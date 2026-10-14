"""Goal Gravity loop: the composition that makes authorized goals attractors.

    Sense -> Experience -> Backcast -> Detect Gate -> Manufacture Leverage
    -> Execute/Prepare/Escalate -> Create Favorable Intersection -> Verify
    -> Compound -> Recalculate -> Repeat

This module composes the canonical machinery on ``main`` (Evidence Ledger,
standing cognition, policy engine, Consequence Gate, causal memory, Capability
Genome registry) with the goal registry, world model, relevance router, GPS
adapter, intervention classifier, intersection detector, retention and
attention router. It introduces no second Kernel, mission authority plane,
identity plane, evidence plane or deliberation engine:

* goals are data on the one ledger; every projection here is folded from
  ledger records (``_sync``), so two loops over one ledger agree;
* when a ``StandingCognitionRuntime`` is attached, every awake goal's
  deliberation runs through its ``tick`` (goal context in, candidates out,
  guardian/treasury vetoes honored, model calls metered by a per-goal
  governor carved out of the caller's ``ResourceGovernor``); without one the
  loop runs in declared-move mode and says so;
* every executed move goes through ``ConsequenceGate.run`` with a
  pre-existing grant supplied by the caller for the duration of one turn; the
  loop holds none afterwards and never constructs an executor; the Gate must
  write to the same ledger;
* evidence references handed to policy are real ledger hashes (the goal's
  authorization record, experience records relevant to the goal, receipts);
  the loop never fabricates a reference or inflates confidence;
* a turn is idempotent per ``trigger_id``; a restart never duplicates a
  consequential action; an attempt whose outcome is unknown stays a blocker
  until ``reconcile`` closes it from the Gate's own records or an accountable
  resolution;
* "externally verified" is never the executor's own claim: ``verify_outcome``
  requires an independent verifier and evidence references;
* dormant goals cost nothing; a hibernating resource governor processes no
  goal at all; a conserving one wakes only priority 1-2 goals and records the
  deferral.

Deviation recorded: ``turn`` accepts ``gate`` and ``executor`` for one turn,
whereas ``StandingCognitionRuntime.tick`` must never accept an executor. The
runtime proposes; the loop is the accountable projection that submits a
selected, policy-allowed move to the Gate. ``goal_gravity_closures`` verifies
that no component retains an executor, a gate or a grant between turns.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Mapping, Sequence

from .acquisition import CapabilityAcquisition
from .advancement import AdvancementMonitor
from .attention import AttentionItem, AttentionPolicy, FounderAttentionRouter, Routing
from .cognition_seam import GoalProposer, cadence_signal, candidate_to_intervention, goal_context
from .competency import GoalCompetencyRouting, RoutingView
from .contracts import ContractError, IntegrityConflict, SignalEnvelope, canonical_copy, digest, require_text
from .experience import WorldModel
from .intake import GoalIntake
from .goals import CONSEQUENCE_CLASSES, GoalRegistry, GoalSpec, InterventionSpec, iso, parse_time
from .gps import BackcastGPSAdapter, GPSFix
from .intersections import FavorableIntersectionDetector, IntersectionReport
from .opportunity import OpportunityPackager
from .interventions import Classification, InterventionClassifier
from .relevance import GoalRelevanceRouter
from .resources import ResourceExhausted, ResourceGovernor, ResourceMode
from .retention import AsymmetryRetention, DurableAsset
from .sensorium import Sensorium

TURN_STATUSES = ("silent", "advanced", "hibernating", "conserving")
ACTIONABLE = ("EXECUTE_AUTONOMOUSLY", "PREPARE_FOR_FOUNDER", "ESCALATE")
OPEN_ATTEMPT_STATES = ("attempted", "unknown")
DONE_STATES = ("executed", "externally_verified")
GATE_TERMINAL_FAILED = ("refused", "denied", "expired", "revoked", "failed")
CONSERVE_PRIORITY_CEILING = 2


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
    deliberation: str = "declared_moves"   # or "standing_cognition"
    deferred: tuple[str, ...] = ()         # goals not woken because the governor is conserving
    derived_signal_ids: tuple[str, ...] = ()   # interoceptive readings integrated this turn (section 8)

    @property
    def execution_authority(self) -> str:
        return "none"

    def to_dict(self) -> dict[str, Any]:
        return canonical_copy({
            "turn_id": self.turn_id, "trigger_id": self.trigger_id, "request_hash": self.request_hash,
            "status": self.status, "at": self.at, "signal_ids": list(self.signal_ids), "woken": list(self.woken),
            "processed": list(self.processed), "executed": list(self.executed), "prepared": list(self.prepared),
            "escalated": list(self.escalated), "routing": self.routing, "resource_snapshot": self.resource_snapshot,
            "experience_surface": self.experience_surface, "deliberation": self.deliberation,
            "deferred": list(self.deferred), "derived_signal_ids": list(self.derived_signal_ids),
            "execution_authority": "none"})

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "GravityTurn":
        return cls(turn_id=value["turn_id"], trigger_id=value["trigger_id"], request_hash=value["request_hash"],
                   status=value["status"], at=value["at"], signal_ids=tuple(value["signal_ids"]),
                   woken=tuple(value["woken"]), processed=tuple(value["processed"]), executed=tuple(value["executed"]),
                   prepared=tuple(value["prepared"]), escalated=tuple(value["escalated"]),
                   routing=canonical_copy(value["routing"]), resource_snapshot=canonical_copy(value["resource_snapshot"]),
                   experience_surface=canonical_copy(value["experience_surface"]),
                   deliberation=value.get("deliberation", "declared_moves"),
                   deferred=tuple(value.get("deferred", ())),
                   derived_signal_ids=tuple(value.get("derived_signal_ids", ())))


class GoalGravityLoop:
    TURN_RECORD = "egregore.gravity_turn"
    TURN_CONFLICT_RECORD = "egregore.gravity_turn_conflict"
    INTERVENTION_RECORD = "egregore.intervention"
    PREPARED_RECORD = "egregore.prepared_work"
    DRIFT_RECORD = "egregore.goal_drift"
    DEFICIT_CLASS_RECORD = "egregore.deficit"
    CANDIDATE_RECORD = "egregore.goal_candidate_bound"
    DISCREPANCY_RECORD = "egregore.outcome_discrepancy"
    RECONCILIATION_RECORD = "egregore.reconciliation"
    VERIFICATION_RECORD = "egregore.outcome_verified"
    MUTED_RECORD = "egregore.signal_not_monitored"

    def __init__(self, *, ledger: Any, compiled: Any, passports: Any, actor: str, legal_principal: str,
                 genomes: Any = None, cognition: Any = None, memory: Any = None,
                 attention_policy: AttentionPolicy | None = None, interoception: bool = True,
                 capability_router: Any = None,
                 source: str = "spiffe://uniimente.internal/egregore/goal-gravity"):
        if not hasattr(ledger, "append") or not hasattr(ledger, "by_type") or not hasattr(ledger, "records"):
            raise ContractError("ledger must provide append(), by_type() and records")
        self.ledger = ledger
        self.source = require_text("source", source)
        if cognition is not None:
            proposers = getattr(cognition, "proposers", {})
            if not any(isinstance(p, GoalProposer) for p in proposers.values()):
                raise ContractError("the standing cognition runtime must register a GoalProposer to deliberate goals")
            if cognition.ledger is not ledger:
                raise ContractError("standing cognition must share the one ledger")
        self.cognition = cognition
        if memory is None:
            from memory.causal import CausalMemory
            memory = CausalMemory(ledger)
        self.memory = memory
        self.registry = GoalRegistry(ledger=ledger, source=source)
        self.world = WorldModel(ledger=ledger, source=source)
        self.genomes = genomes
        self.router = GoalRelevanceRouter(self.registry)
        self.gps = BackcastGPSAdapter(ledger=ledger, world=self.world, genomes=genomes, memory=memory, source=source)
        self.classifier = InterventionClassifier(ledger=ledger, registry=self.registry, compiled=compiled,
                                                 passports=passports, actor=actor, legal_principal=legal_principal,
                                                 source=source)
        self.detector = FavorableIntersectionDetector(ledger=ledger, world=self.world, source=source)
        self.retention = AsymmetryRetention(ledger=ledger, registry=self.registry, genomes=genomes, source=source) if genomes is not None else None
        self.attention = FounderAttentionRouter(ledger=ledger, registry=self.registry, policy=attention_policy, source=source)
        self.advancement = AdvancementMonitor(ledger=ledger, registry=self.registry, turn_record=self.TURN_RECORD,
                                              prepared_record=self.PREPARED_RECORD, source=source)
        self.sensorium = Sensorium(self) if interoception else None
        self.opportunity = OpportunityPackager(ledger=ledger, world=self.world, classifier=self.classifier, source=source)
        self.acquisition = CapabilityAcquisition(self)
        self.intake = GoalIntake(self)
        # The Competency Compiler (capabilities/router.py on main): optional; without it gates are unrouted.
        self.competency = (GoalCompetencyRouting(capability_router, ledger=ledger, genomes=genomes)
                           if capability_router is not None else None)
        self._turns: dict[str, GravityTurn] = {}
        self._interventions: list[dict[str, Any]] = []
        self._decisions: dict[tuple[str, str], str] = {}   # (goal_id, route_hash) -> latest classification
        self._folded = 0
        self._sync()

    @property
    def execution_authority(self) -> str:
        return "none"

    # ------------------------------------------------------------ ledger projection
    def _sync(self) -> None:
        """Fold ledger records appended since the last fold (by this loop, another loop, the Gate, retention).

        Every projection is a fold of the one ledger, so two loops over one ledger agree on goals, beliefs,
        asks, intersections, retained genomes, routing track records, turns and interventions."""
        for component in (getattr(self, "registry", None), getattr(self, "world", None), getattr(self, "attention", None),
                          getattr(self, "detector", None), getattr(self, "retention", None)):
            if component is not None:
                component.sync()
        if getattr(self, "competency", None) is not None:
            self.competency.refresh()
        records = self.ledger.records
        for record in records[self._folded:]:
            rtype = getattr(record, "record_type", None)
            if rtype == self.TURN_RECORD:
                turn = GravityTurn.from_dict(record.payload["turn"])
                self._turns[turn.trigger_id] = turn
            elif rtype == self.INTERVENTION_RECORD:
                self._interventions.append(canonical_copy(record.payload))
            elif rtype == InterventionClassifier.CLASSIFICATION_RECORD:
                c = record.payload["classification"]
                self._decisions[(c["goal_id"], c["route_hash"])] = c["decision"]
        self._folded = len(records)

    def _latest_by_route(self, goal_id: str) -> dict[str, dict[str, Any]]:
        latest: dict[str, dict[str, Any]] = {}
        for item in self._interventions:
            if item["goal_id"] == goal_id:
                latest[item["intervention"]["route_hash"]] = item
        return latest

    def _record_intervention(self, goal_id: str, intervention: InterventionSpec, *, classification_id: str,
                             decision: str, evidence_state: str, detail: Mapping[str, Any] | None = None,
                             now: str) -> dict[str, Any]:
        payload = {"source": self.source, "goal_id": goal_id, "intervention": intervention.to_dict(),
                   "classification_id": classification_id, "decision": decision,
                   "evidence_state": evidence_state, "detail": canonical_copy(dict(detail or {})), "at": now}
        self.ledger.append(self.INTERVENTION_RECORD, payload)
        self._sync()
        return canonical_copy(payload)

    def _record_deficit(self, goal_id: str, deficit_class: str, detail: str, *, now: str) -> dict[str, Any]:
        entry = {"class": deficit_class, "detail": detail}
        self.ledger.append(self.DEFICIT_CLASS_RECORD, {"source": self.source, "goal_id": goal_id, **entry, "at": now,
                                                       "disposition": "goal_blocked_not_closed"})
        return entry

    def _last_intersection_favorable(self, goal_id: str) -> bool:
        """Whether the most recent recorded turn that processed the goal saw a favorable intersection."""
        for turn in reversed(list(self._turns.values())):
            for processed in turn.processed:
                if processed["goal_id"] == goal_id and "intersection" in processed:
                    return bool(processed["intersection"].get("favorable"))
        return False

    def _already_attempted(self, goal_id: str, route_hash: str) -> dict[str, Any] | None:
        """The route's latest record decides: a ``failed`` after an ``attempted`` releases the route."""
        item = self._latest_by_route(goal_id).get(route_hash)
        if item is not None and item["evidence_state"] in OPEN_ATTEMPT_STATES + DONE_STATES:
            return item
        return None

    # ------------------------------------------------------------ evidence, budget, dependencies
    def _evidence(self, goal_id: str, state: Any, caller_confidence: float) -> tuple[list[str], float, str]:
        """Real evidence only: authorization record hash, relevant experience records, receipts.

        Confidence is the relevance-weighted belief confidence of the goal's world evidence, capped by
        the accountable caller's attestation; with no world evidence the caller's value stands alone and
        is labelled as such. Nothing here raises confidence above either source.
        """
        refs, derived = self.world.evidence_for_goal(goal_id)
        auth = self.registry.authorization_hash(goal_id)
        all_refs = list(dict.fromkeys(([auth] if auth else []) + refs + list(state.evidence_refs)))
        caller = float(caller_confidence)
        if refs:
            return all_refs, round(min(caller, derived), 6), "world_model_capped_by_caller"
        return all_refs, round(caller, 6), "caller_attested_only"

    @staticmethod
    def _goal_governor(spec: GoalSpec, resources: ResourceGovernor) -> ResourceGovernor:
        """Per-goal budget (section 14 ``resource_budget``) carved out of the turn's remaining budget."""
        budget = spec.resource_budget or {}
        calls = min(int(budget.get("max_model_calls", 0)), resources.max_model_calls - resources.used_model_calls)
        cost = min(float(budget.get("max_estimated_cost_usd", 0.0)),
                   resources.max_estimated_cost_usd - resources.used_estimated_cost_usd)
        return ResourceGovernor(max_model_calls=max(calls, 0), max_estimated_cost_usd=max(cost, 0.0),
                                conservation_threshold=resources.conservation_threshold)

    @staticmethod
    def _charge(resources: ResourceGovernor, child: ResourceGovernor, goal_id: str) -> dict[str, Any]:
        used = child.used_model_calls
        per_call = (child.used_estimated_cost_usd / used) if used else 0.0
        for _ in range(used):
            remaining = max(resources.max_estimated_cost_usd - resources.used_estimated_cost_usd, 0.0)
            resources.consume_call(component=f"goal:{goal_id[7:23]}", estimated_cost_usd=min(per_call, remaining))
        return {"model_calls": used, "estimated_cost_usd": round(child.used_estimated_cost_usd, 6),
                "goal_ceiling": {"max_model_calls": child.max_model_calls,
                                 "max_estimated_cost_usd": child.max_estimated_cost_usd}}

    def _unmet_dependencies(self, spec: GoalSpec) -> list[str]:
        known = set(self.registry.goals())
        unmet = []
        for dep in spec.dependencies:
            if dep in known:
                status = self.registry.state(dep).status
                if status != "completed":
                    unmet.append(f"{dep[:23]} is {status}")
            else:
                unmet.append(f"{dep} is not a registered goal")
        return unmet

    @staticmethod
    def _marginal_value(spec: GoalSpec, intervention: InterventionSpec, priority: int) -> float:
        """Attention leverage: higher priority and higher consequence => more value in asking."""
        consequence = CONSEQUENCE_CLASSES.index(intervention.consequence_class) / (len(CONSEQUENCE_CLASSES) - 1)
        return round(min(1.0, 0.35 + 0.4 * ((6 - priority) / 5) + 0.25 * consequence), 3)

    # ------------------------------------------------------------ attention items
    def _ask_for(self, spec: GoalSpec, intervention: InterventionSpec, classification: Classification,
                 *, kind: str, urgency: str, now: str, fix: GPSFix, evidence_refs: Sequence[str]) -> AttentionItem:
        priority = self.registry.effective_priority(spec.goal_id)
        options = ({"label": "authorize this move", "cost": f"{intervention.estimated_cost_usd} USD estimated"},
                   {"label": "revise the route", "cost": "none"},
                   {"label": "do nothing now", "cost": "none"})
        refs = tuple(evidence_refs[-5:])
        return AttentionItem.build(
            goal_id=spec.goal_id, kind=kind, urgency=urgency,
            marginal_value=self._marginal_value(spec, intervention, priority),
            title=f"{spec.desired_state[:60]}: {intervention.description[:60]}",
            question=f"Gate '{fix.active_gate}' is active. GREG recorded a candidate move "
                     f"'{intervention.description}' ({intervention.consequence_class}); it was not executed. "
                     f"Reasons: {'; '.join(classification.reasons)}. Your decision?",
            options=options,
            recommendation="authorize if the cited evidence is sufficient; otherwise revise or do nothing",
            evidence_refs=refs,
            effort_estimate=f"read {len(refs)} evidence reference(s); one decision among {len(options)} options; "
                            f"nothing else is required unless you choose to act",
            category=intervention.consequence_class, created_at=now,
            route_hash=intervention.route_hash, tactic=intervention.tactic or None,
            effect_hash=intervention.effect_hash)

    def _inform(self, spec: GoalSpec, *, title: str, text: str, urgency: str, evidence_refs: Sequence[str],
                now: str, marginal_value: float, category: str = "information") -> AttentionItem:
        """'Alfonso should know': information items request nothing and always cost nothing."""
        return AttentionItem.build(
            goal_id=spec.goal_id, kind="information", urgency=urgency, marginal_value=min(1.0, marginal_value),
            title=f"{spec.desired_state[:60]}: {title}"[:160], question=text,
            options=({"label": "noted", "cost": "none"}, {"label": "raise this goal's priority", "cost": "none"}),
            recommendation="no action needed; GREG continues within its authority",
            evidence_refs=tuple(evidence_refs[:5]), effort_estimate="none", category=category, created_at=now)

    def _inform_intersection(self, spec: GoalSpec, report: IntersectionReport, *, now: str,
                             package: Mapping[str, Any] | None = None) -> AttentionItem:
        quantified = [f"{s['factor_id']} {s['quantified']['relative_improvement']:+.0%}"
                      for s in (package or {}).get("satisfied", [])
                      if s.get("quantified") and s["quantified"].get("relative_improvement") is not None]
        need = sum(1 for o in (package or {}).get("options", []) if o["without_a_grant"] in ("PREPARE_FOR_FOUNDER", "ESCALATE"))
        text = (f"{len(report.satisfied)} weak signals across {', '.join(report.domains)} converged "
                f"(score {report.score:.2f} vs threshold {report.threshold:.2f})")
        if quantified:
            text += "; measured against baselines: " + ", ".join(quantified)
        if package and package.get("contested"):
            text += f"; {len(package['contested'])} contested factor(s) kept out of the score"
        if package:
            text += f". Opportunity package {package['package_id'][7:19]} lists {len(package['options'])} move(s): {need} need you"
        text += ". No action is requested."
        return self._inform(spec, title="favorable intersection", urgency="low", now=now,
                            marginal_value=0.2 + 0.1 * len(report.domains), text=text,
                            evidence_refs=(package or {}).get("evidence_refs") or [s["signal_id"] for s in report.satisfied])

    def _route(self, spec: GoalSpec, fix: GPSFix, *, now: str, items: list, blockers: list) -> RoutingView | None:
        """Route the active gate through the Competency Compiler and surface what it means."""
        if fix.active_node_id is None:
            return None
        node = spec.node(fix.active_node_id)
        if self.competency is None:
            # Without the router a human-only gate (authorization, legal) is still recognised from the
            # canonical taxonomy, so it surfaces as one founder decision instead of stalling silently.
            from capabilities.router import HUMAN_ONLY_METHODS, PROBLEM_CLASSES
            if node.problem_class is None:
                return None
            methods = set(PROBLEM_CLASSES[node.problem_class]["any_of"]) | set(PROBLEM_CLASSES[node.problem_class]["all_of"])
            if not methods or not methods <= HUMAN_ONLY_METHODS:
                return None
            view = RoutingView(decision_id=digest({"kind": "egregore-human-gate", "goal_id": spec.goal_id, "node_id": node.node_id}),
                               problem_id=digest({"kind": "egregore-routing-problem", "goal_id": spec.goal_id, "node_id": node.node_id}),
                               problem_class=node.problem_class, selected=(), expected_evidence={},
                               human_escalation=tuple(sorted(methods)), exploratory=False, requires_gate=False,
                               rejected={}, deficit=None)
            items.append(self._human_gate_item(spec, node, view, now=now))
            return view
        try:
            routing = self.competency.route_gate(spec, fix)
        except Exception as exc:   # a refused route is retained as a blocker and every move waits
            if node.problem_class is None:
                return None
            reason = f"routing refused: {type(exc).__name__}: {exc}"[:200]
            blockers.append(f"capability deficit: {reason}")
            return RoutingView(decision_id=digest({"kind": "egregore-routing-refused", "goal_id": spec.goal_id,
                                                   "node_id": node.node_id, "reason": reason}),
                               problem_id=digest({"kind": "egregore-routing-problem", "goal_id": spec.goal_id,
                                                  "node_id": node.node_id}),
                               problem_class=node.problem_class, selected=(), expected_evidence={}, human_escalation=(),
                               exploratory=False, requires_gate=False, rejected={},
                               deficit={"router_deficit_id": digest({"kind": "egregore-router-refusal", "reason": reason}),
                                        "problem_class": node.problem_class, "missing_methods": [reason], "rejected": {},
                                        "authority": "none"})
        if routing is None:
            return None
        if routing.deficit is not None:
            blockers.append(f"capability deficit: epistemic: no mechanism offers {', '.join(routing.deficit['missing_methods'])} "
                            f"for this {routing.problem_class} gate")
        else:
            self._resolve_epistemic_deficits(spec, node.node_id, routing, now=now)
        if routing.human_escalation:
            items.append(self._human_gate_item(spec, node, routing, now=now))
        if routing.preferred_instead:
            items.append(self._inform(spec, title="better mechanism available", urgency="low", now=now, marginal_value=0.4,
                                      text=f"For gate '{node.gate}' the Competency Compiler would recruit "
                                           f"{', '.join(routing.preferred_instead)} instead of the declared "
                                           f"{', '.join(node.requires_capabilities)}. The declared plan still governs.",
                                      evidence_refs=[], category="competency"))
        return routing

    def _resolve_epistemic_deficits(self, spec: GoalSpec, node_id: str, routing: RoutingView, *, now: str) -> None:
        """A gate that now routes closes its open epistemic deficit; the original goal resumes."""
        latest: dict[str, dict[str, Any]] = {}
        for r in self.ledger.by_type(self.classifier.DEFICIT_RECORD):
            d = r.payload.get("deficit") or {}
            if d.get("goal_id") == spec.goal_id and d.get("active_node_id") == node_id and d.get("missing_methods"):
                latest[d["deficit_id"]] = d
        from .contract_check import validate_record
        for d in latest.values():
            if d["disposition"] != "goal_blocked_not_closed":
                continue
            closed = {**d, "lifecycle": "TESTED", "disposition": "resolved_resume_original_goal", "resolved_at": now,
                      "resolved_by": f"competency:{routing.decision_id[7:23]}:{','.join(routing.selected)}"[:200]}
            validate_record(closed, "capability-deficit")
            self.ledger.append(self.classifier.DEFICIT_RECORD, {
                "source": self.source, "deficit": closed, "goal_id": spec.goal_id, "missing_capabilities": [],
                "founder_intent": closed["founder_intent"], "disposition": closed["disposition"]})

    def _human_gate_item(self, spec: GoalSpec, node: Any, routing: RoutingView, *, now: str) -> AttentionItem:
        """Only a person can answer this gate. One stable decision item; accepting records typed evidence."""
        method = routing.human_escalation[0]
        priority = self.registry.effective_priority(spec.goal_id)
        return AttentionItem.build(
            goal_id=spec.goal_id, kind="decision", urgency="normal",
            marginal_value=round(min(1.0, 0.55 + 0.4 * ((6 - priority) / 5)), 3),
            title=f"{spec.desired_state[:60]}: {node.gate[:60]}",
            question=(f"Gate '{node.gate}' poses a {routing.problem_class} question that only a person can answer "
                      f"({', '.join(routing.human_escalation)}). Accepting records your decision as evidence for "
                      f"{node.sbm}; it is not a grant and executes nothing."),
            options=({"label": "accept (record my decision)", "cost": "one decision"},
                     {"label": "refuse", "cost": "none"}, {"label": "do nothing now", "cost": "none"}),
            recommendation="decide when the prepared work and evidence for this gate are sufficient",
            evidence_refs=tuple(r for r in (self.registry.authorization_hash(spec.goal_id),) if r),
            effort_estimate="one decision; GREG prepares everything else", category=routing.problem_class,
            created_at=now, evidence_on_accept={"sbm": node.sbm, "value": node.sbm_target, "method": method,
                                                "node_id": node.node_id, "routing_decision_id": routing.decision_id})

    def _advancement_item(self, spec: GoalSpec, report: Mapping[str, Any], *, now: str) -> AttentionItem:
        """The section-5 report: one compressed entry point, never a reminder, always cheap to decline."""
        decisions = report["open_decisions"]
        options = ([{"label": "review the prepared decision(s)", "cost": f"{len(decisions)} decision(s)"}] if decisions else []) + [
            {"label": "lower this goal's priority", "cost": "none"},
            {"label": "pause this goal", "cost": "none"},
            {"label": "do nothing now", "cost": "none"}]
        priority = self.registry.effective_priority(spec.goal_id)
        return AttentionItem.build(
            goal_id=spec.goal_id, kind="decision" if decisions else "information", urgency="normal",
            marginal_value=round(min(1.0, 0.45 + 0.4 * ((6 - priority) / 5)), 3),
            title=f"{spec.desired_state[:60]}: progress report", question=report["text"], options=options,
            recommendation=("the prepared decision is the shortest path past the main friction" if decisions
                            else "no action needed; GREG keeps working within its authority"),
            evidence_refs=tuple(report["evidence_refs"]), effort_estimate=report["effort"], category="advancement",
            created_at=now)

    # ------------------------------------------------------------ drift and gate observation
    def drift_report(self, goal_id: str) -> dict[str, Any]:
        """Observed execution versus the authorized plan: unknown routes are visible drift.

        Convention: goal-originated proposals carry ``proposal_id == "egregore:goal:<goal23>:<route23>"``;
        the Gate's own ``action.committed`` events are the observation source.
        """
        spec = self.registry.get(goal_id)
        planned = {i.route_hash[:23] for n in spec.plan for i in n.interventions}
        prefix = f"egregore:goal:{goal_id[:23]}:"
        observed, drifted = [], []
        for record in self.ledger.by_type("event"):
            p = record.payload
            if p.get("type") == "action.committed" and str(p.get("proposal_id", "")).startswith(prefix):
                route = p["proposal_id"][len(prefix):].split(":r", 1)[0]   # drop a re-dispatch suffix
                observed.append(route)
                if route not in planned:
                    drifted.append(route)
        return {"goal_id": goal_id, "observed_routes": observed, "drifted_routes": drifted, "drift": bool(drifted)}

    def _gate_observation(self, proposal_id: str) -> dict[str, Any] | None:
        """What the Gate's own ledger events say happened to a proposal (latest action.* event)."""
        latest: dict[str, Any] | None = None
        for record in self.ledger.by_type("event"):
            p = record.payload
            if p.get("proposal_id") == proposal_id and str(p.get("type", "")).startswith("action."):
                latest = {"state": p["type"][len("action."):], "action_id": p.get("action_id"),
                          "outcome_id": p.get("outcome_id"), "reasons": list(p.get("reasons", [])),
                          "record_hash": record.hash}
        if latest and latest["state"] == "recorded":
            for record in self.ledger.by_type("outcome"):
                if record.payload.get("outcome_id") == latest["outcome_id"]:
                    latest["outcome"] = canonical_copy(record.payload)
                    latest["outcome_hash"] = record.hash
            for record in self.ledger.by_type("receipt"):
                if record.payload.get("action_id") == latest["action_id"]:
                    latest["receipt_hash"] = record.hash
        return latest

    # ------------------------------------------------------------ deliberation seam
    def _candidates_for(self, spec: GoalSpec, fix: GPSFix, *, trigger_id: str, signal_ids: Sequence[str],
                        resources: ResourceGovernor, call_costs: Mapping[str, float] | None, at: str
                        ) -> tuple[list[InterventionSpec], str | None, dict[str, Any]]:
        """Candidate moves: from the standing-cognition tick when attached, else the declared moves."""
        if self.cognition is None:
            return [InterventionSpec.from_dict(raw) for raw in fix.next_interventions], None, {"mode": "declared_moves"}
        context = goal_context(spec, fix, trigger_id=trigger_id, priority=self.registry.effective_priority(spec.goal_id))
        child = self._goal_governor(spec, resources)
        cycle = self.cognition.tick(trigger_id=f"{trigger_id}:goal:{spec.goal_id[7:23]}", signal_ids=tuple(signal_ids),
                                    resources=child, context=context, call_costs=call_costs)
        usage = self._charge(resources, child, spec.goal_id)
        moves: list[InterventionSpec] = []
        selected_route: str | None = None
        for candidate in cycle.candidates:
            move = candidate_to_intervention(candidate)
            is_selected = candidate.candidate_id == cycle.selected_candidate_id
            if is_selected:
                selected_route = move.route_hash
            self.ledger.append(self.CANDIDATE_RECORD, {
                "source": self.source, "goal_id": spec.goal_id, "cycle_id": cycle.cycle_id,
                "candidate_id": candidate.candidate_id, "proposed_by": candidate.proposed_by,
                "intervention_id": move.intervention_id, "route_hash": move.route_hash,
                "selected": is_selected, "at": at})
            moves.append(move)
        return moves, selected_route, {"mode": "standing_cognition", "cycle_id": cycle.cycle_id,
                                       "cycle_status": cycle.status.value, "candidates": len(moves),
                                       "vetoes": sum(1 for a in cycle.assessments if a.veto),
                                       "failures": len(cycle.failures), "resource_usage": usage}

    # ------------------------------------------------------------ the loop
    def turn(self, *, trigger_id: str, now: datetime | str, signals: Sequence[SignalEnvelope] = (),
             resources: ResourceGovernor, grants: Mapping[str, Mapping[str, Any]] | None = None,
             gate: Any = None, executor: Callable[[Any], dict] | None = None,
             evidence_confidence: float = 0.0, call_costs: Mapping[str, float] | None = None) -> GravityTurn:
        trigger_id = require_text("trigger_id", trigger_id)
        if not isinstance(resources, ResourceGovernor):
            raise ContractError("resources must be a ResourceGovernor")
        if gate is not None and getattr(gate, "ledger", None) is not self.ledger:
            raise ContractError("the Consequence Gate must write to the one ledger this loop reads")
        if executor is not None and gate is None:
            raise ContractError("an executor is admitted only through a Consequence Gate")
        self._sync()
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

        # 1. Sense -> Experience: every signal becomes a provenance-backed experience. Caller signals first,
        #    then the institution's own derived modalities (section 8), emitted only when a value changed.
        wake_requests: dict[str, list[str]] = {}
        relevant_signals: dict[str, list[str]] = {}
        touched_keys: set[str] = set()

        def sense(signal: SignalEnvelope) -> None:
            observations = self.world.observations_from_signal(signal)
            verdicts = self.router.route(signal, observations=observations)
            domain = signal.payload.get("domain")
            muting = [g for g in self.registry.goals() if self.registry.domain_muted(g, domain)]
            if muting and not any(v.score > 0 and not self.registry.domain_muted(g, domain) for g, v in verdicts.items()):
                # "Do not monitor this domain": the signal is not integrated, ingested or retained; only the fact
                # that a muted-domain signal arrived is recorded, without its content.
                self.ledger.append(self.MUTED_RECORD, {"source": self.source, "signal_id": signal.signal_id,
                                                       "domain": domain, "muted_by": sorted(muting), "at": at,
                                                       "disposition": "not integrated: founder do_not_monitor"})
                return
            if self.cognition is not None:
                self.cognition.ingest(signal)
            touched_keys.update(o.key for o in observations)
            woke_here = [g for g, v in verdicts.items() if v.wake]
            self.world.integrate(signal, now=at, goal_relevance={g: v.score for g, v in verdicts.items()},
                                 context={"trigger_id": trigger_id}, attention=woke_here)
            for goal_id, verdict in verdicts.items():
                relevant_signals.setdefault(goal_id, []).append(signal.signal_id)
                if verdict.wake:
                    wake_requests.setdefault(goal_id, []).append(signal.signal_id)

        for signal in ordered_signals:
            sense(signal)
        derived = self.sensorium.signals(at) if self.sensorium is not None else []
        for signal in derived:
            sense(signal)
        hibernating = resources.mode is ResourceMode.HIBERNATE
        conserving = resources.mode is ResourceMode.CONSERVE
        # Individually weak signals may still combine: a favorable intersection wakes a goal.
        intersection_wakes: dict[str, IntersectionReport] = {}
        if not hibernating:
            for goal_id in self.registry.goals():
                if goal_id in wake_requests:
                    continue
                spec = self.registry.get(goal_id)
                state = self.registry.state(goal_id)
                if not spec.opportunity_factors or state.status not in ("dormant", "blocked") or state.preferences.get("stop_pushing"):
                    continue
                if not any(f"{f.subject}.{f.attribute}" in touched_keys for f in spec.opportunity_factors):
                    continue
                report = self.detector.detect(spec, now=at, muted_domains=state.preferences.get("do_not_monitor", []))
                if report.favorable:
                    intersection_wakes[goal_id] = report

        # 2. Wake: relevant evidence, favorable intersection or cadence; never when hibernating; while
        #    conserving only priority 1-2 goals wake and every deferral is recorded.
        woken: list[str] = []
        deferred: list[str] = []
        if not hibernating:
            wake_plan: list[tuple[str, str, list[str]]] = []
            for goal_id, signal_ids in wake_requests.items():
                wake_plan.append((goal_id, f"relevant evidence: {len(signal_ids)} signal(s)", signal_ids))
            for goal_id, report in intersection_wakes.items():
                wake_plan.append((goal_id, f"favorable intersection (score={report.score:.2f})", []))
            planned_ids = {g for g, _, _ in wake_plan}
            for goal_id in self.registry.due_for_review(at):
                if goal_id not in planned_ids:
                    wake_plan.append((goal_id, "review cadence elapsed", []))
                    planned_ids.add(goal_id)
            for goal_id in self.registry.by_status("awake"):
                if goal_id not in planned_ids:
                    wake_plan.append((goal_id, "", []))
            for goal_id, reason, signal_ids in wake_plan:
                if conserving and self.registry.effective_priority(goal_id) > CONSERVE_PRIORITY_CEILING:
                    deferred.append(goal_id)
                    self._record_deficit(goal_id, "resource", "resource governor conserving; non-critical goal not woken", now=at)
                    continue
                if reason and self.registry.state(goal_id).status != "awake":
                    self.registry.wake(goal_id, reason=reason, now=at, signal_ids=signal_ids)
                woken.append(goal_id)
        woken = sorted(dict.fromkeys(woken), key=lambda g: (self.registry.effective_priority(g), g))

        processed, executed, prepared, escalated, items = [], [], [], [], []
        for goal_id in woken:
            spec = self.registry.get(goal_id)
            state = self.registry.state(goal_id)
            summary: dict[str, Any] = {"goal_id": goal_id, "priority": self.registry.effective_priority(goal_id)}
            # 3. Backcast -> active gate -> SBM (moves ordered by ledgered precedent when any exists).
            fix = self.gps.fix(spec, state, now=at)
            summary.update({"active_node_id": fix.active_node_id, "active_gate": fix.active_gate, "sbm": fix.sbm,
                            "missing_capabilities": list(fix.missing_capabilities),
                            "missing_relationships": list(fix.missing_relationships),
                            "route_changed": fix.route_changed, "complete": fix.complete})
            if fix.complete:
                self.registry.transition(goal_id, reason="all plan nodes satisfied by observed evidence", now=at,
                                         status="completed", current_state=fix.current_position,
                                         active_node_id=None, active_gate=None, sbm=None, blockers=[], deficits=[])
                summary["decisions"] = []
                processed.append(summary)
                continue
            evidence_refs, confidence, evidence_basis = self._evidence(goal_id, state, evidence_confidence)
            summary["evidence"] = {"refs": len(evidence_refs), "confidence": confidence, "basis": evidence_basis}
            # 4. Favorable intersections are observed and reported, never acted on directly.
            report: IntersectionReport | None = None
            if spec.opportunity_factors:
                report = intersection_wakes.get(goal_id) or self.detector.detect(
                    spec, now=at, muted_domains=state.preferences.get("do_not_monitor", []))
                summary["intersection"] = {"score": report.score, "favorable": report.favorable,
                                           "domains": list(report.domains), "threat_score": report.threat_score,
                                           "threats": [t["factor_id"] for t in report.threats]}
                # Inform when the intersection becomes favorable (the transition is the news); a still-favorable
                # intersection is status in the turn record and status(), not a fresh interruption.
                if report.favorable and (goal_id in intersection_wakes or not self._last_intersection_favorable(goal_id)):
                    package = self.opportunity.package(
                        spec, state, report, fix, moves=[InterventionSpec.from_dict(m) for m in fix.next_interventions],
                        evidence_refs=evidence_refs, confidence=confidence, now=at)
                    summary["opportunity_package"] = package["package_id"]
                    items.append(self._inform_intersection(spec, report, now=at, package=package))
            # 5. Discrepancies are made visible before any new move: drift, contradicted SBM, open attempts.
            drift = self.drift_report(goal_id)
            if drift["drift"]:
                self.ledger.append(self.DRIFT_RECORD, {"source": self.source, **drift, "at": at,
                                                       "disposition": "discrepancy_visible_not_hidden"})
                summary["drift"] = drift["drifted_routes"]
                items.append(self._inform(spec, title="execution drift", urgency="high", now=at, marginal_value=0.9,
                                          text=f"{len(drift['drifted_routes'])} committed route(s) are outside the authorized plan: "
                                               f"{', '.join(r[:16] for r in drift['drifted_routes'])}. Nothing new was executed.",
                                          evidence_refs=evidence_refs, category="discrepancy"))
            if fix.sbm:
                belief = self.world.belief_by_key(fix.sbm["name"])
                if belief is not None and belief.contradicted:
                    summary["sbm_contradicted"] = True
                    items.append(self._inform(spec, title="bottleneck metric contradicted", urgency="normal", now=at,
                                              marginal_value=0.6,
                                              text=f"Sources disagree on {fix.sbm['name']}; both readings are retained and the "
                                                   f"gate is not treated as satisfied.",
                                              evidence_refs=[r for r in (belief.record_hash,) if r], category="discrepancy"))
            blockers = list(fix.blockers)
            latest = self._latest_by_route(goal_id)
            open_attempts = [r for r, item in latest.items() if item["evidence_state"] in OPEN_ATTEMPT_STATES]
            for route in open_attempts:
                item = latest[route]
                blockers.append(f"reconciliation required: route {route[7:23]} outcome unknown")
                consequence = item["intervention"]["consequence_class"]
                external = CONSEQUENCE_CLASSES.index(consequence) >= CONSEQUENCE_CLASSES.index("external_contact")
                items.append(self._inform(spec, title="outcome unknown", urgency="emergency" if external else "high",
                                          now=at, marginal_value=1.0 if external else 0.8,
                                          text=f"Move '{item['intervention']['description']}' ({consequence}) was dispatched and its "
                                               f"outcome is unknown. It will not be retried; reconcile() closes it from the Gate's "
                                               f"records or an accountable resolution.",
                                          evidence_refs=evidence_refs, category="reconciliation"))
            summary["open_attempts"] = [r for r in open_attempts]
            # 6. Deficits of every class the directive names (section 21): capability, resource, relationship, proof.
            deficits: list[dict[str, Any]] = []
            for cap in fix.missing_capabilities:
                deficits.append(self._record_deficit(goal_id, "capability", cap, now=at))
            for rel in fix.missing_relationships:
                deficits.append(self._record_deficit(goal_id, "relationship", f"no established relationship with {rel}", now=at))
                blockers.append(f"relationship deficit: {rel}")
            unmet = self._unmet_dependencies(spec)
            summary["unmet_dependencies"] = list(unmet)
            for dep in unmet:
                deficits.append(self._record_deficit(goal_id, "proof", f"dependency unmet: {dep}", now=at))
                blockers.append(f"dependency unmet: {dep}")
            # 6b. Competency Compiler: which registered mechanism can answer this gate, with what evidence type?
            routing = self._route(spec, fix, now=at, items=items, blockers=blockers)
            summary["routing"] = routing.to_dict() if routing is not None else {"status": "unrouted"}
            # 7. Deliberate: standing cognition when attached, declared moves otherwise. Classify every candidate;
            #    execute at most one, through the Gate only.
            signal_ids = list(relevant_signals.get(goal_id, []))
            if self.cognition is not None and not signal_ids:
                clock = cadence_signal(goal_id, at=at, source=self.source)
                self.cognition.ingest(clock)
                signal_ids = [clock.signal_id]
            try:
                moves, selected_route, deliberation = self._candidates_for(
                    spec, fix, trigger_id=trigger_id, signal_ids=signal_ids, resources=resources, call_costs=call_costs, at=at)
            except (ContractError, ResourceExhausted, RuntimeError) as exc:  # refusal/conflict is retained, never hidden
                moves, selected_route = [], None
                deliberation = {"mode": "standing_cognition", "error": f"{type(exc).__name__}: {exc}"[:200]}
                blockers.append(f"standing cognition refused: {type(exc).__name__}")
            if deliberation.get("mode") == "standing_cognition" and not moves:
                status_word = deliberation.get("cycle_status", "refused")
                if status_word in ("hibernating", "conserving"):
                    deficits.append(self._record_deficit(goal_id, "resource",
                                                         f"goal resource budget {status_word} for this turn; no candidates deliberated", now=at))
                    blockers.append(f"goal resource budget {status_word}")
                elif status_word == "suspended":
                    blockers.append("standing cognition suspended")
            summary["deliberation"] = deliberation
            decisions: list[dict[str, Any]] = []
            executed_this_goal = False
            for intervention in moves:
                grant = grants.get(intervention.requested_capability)
                grant_view = None
                if grant is not None and gate is not None and hasattr(gate, "grants"):
                    stage = gate.grants.get_meta(grant.get("grant_id", "")).get("stage")
                    grant_view = {**grant, "stage": stage} if stage else grant
                if grant is not None and intervention.estimated_cost_usd > float(grant.get("spending_limit_usd", 0.0)):
                    deficits.append(self._record_deficit(goal_id, "resource",
                                                         f"{intervention.intervention_id}: estimated cost exceeds grant spending limit", now=at))
                selected = None if self.cognition is None else (intervention.route_hash == selected_route)
                classification = self.classifier.classify(
                    spec, state, intervention, fix=fix, grant=grant, grant_view=grant_view,
                    evidence_refs=evidence_refs, evidence_confidence=confidence, now=at, selected=selected,
                    unmet_dependencies=unmet, routing=routing)
                entry = {"intervention_id": intervention.intervention_id, "decision": classification.decision,
                         "reasons": list(classification.reasons), "selected_by_deliberation": selected,
                         "evidence_confidence": confidence, "evidence_basis": evidence_basis}
                routed = ({"routing_decision_id": routing.decision_id, "routed_mechanisms": list(routing.selected),
                           "expected_evidence": dict(routing.expected_evidence)} if routing is not None and routing.routed else {})
                record = lambda evidence_state, detail=None: self._record_intervention(  # noqa: E731
                    goal_id, intervention, classification_id=classification.classification_id,
                    decision=classification.decision, evidence_state=evidence_state,
                    detail={**routed, **dict(detail or {})}, now=at)
                if classification.decision == "EXECUTE_AUTONOMOUSLY":
                    prior = self._already_attempted(goal_id, intervention.route_hash)
                    if prior is not None:
                        entry["evidence_state"] = prior["evidence_state"]
                        entry["note"] = "already attempted; no duplicate consequential action"
                    elif executed_this_goal or gate is None or executor is None or open_attempts:
                        note = ("reconciliation pending for this goal" if open_attempts else
                                "execution deferred: one move per goal per turn, or no gate/executor supplied")
                        record("planned", {"note": note})
                        entry["evidence_state"] = "planned"
                    else:
                        attempt = sum(1 for i in self._interventions if i["goal_id"] == goal_id
                                      and i["intervention"]["route_hash"] == intervention.route_hash
                                      and i["evidence_state"] == "attempted")
                        proposal = self.classifier.proposal_for(spec, intervention, evidence_refs=evidence_refs,
                                                                evidence_confidence=confidence, attempt=attempt)
                        record("attempted", {"proposal_id": proposal.proposal_id, "attempt": attempt})
                        try:
                            action = gate.run(proposal, executor=executor, standing_grant=grant)
                        except Exception as exc:  # the attempt is retained; nothing is retried blindly
                            record("unknown", {"proposal_id": proposal.proposal_id,
                                               "error": f"{type(exc).__name__}: {exc}"[:200]})
                            entry["evidence_state"] = "unknown"
                            blockers.append("gate outcome unknown; reconciliation required")
                            executed_this_goal = True
                            decisions.append(entry)
                            continue
                        if action.state == "recorded":
                            outcome = action.outcome or {}
                            detail = {"action_id": action.action_id, "receipt_hash": action.receipt_hash,
                                      "outcome_id": outcome.get("outcome_id"), "result_class": outcome.get("result_class"),
                                      "executor_claimed_validation": outcome.get("validation_status"),
                                      "expected_vs_actual": outcome.get("expected_vs_actual")}
                            record("executed", detail)   # never "externally_verified" on the executor's own word
                            state.evidence_refs = list(state.evidence_refs) + [action.receipt_hash]
                            executed.append({"goal_id": goal_id, **detail, **routed, "evidence_state": "executed"})
                            entry["evidence_state"] = "executed"
                            reconciled = "reconciled=True" in str(outcome.get("expected_vs_actual", ""))
                            if outcome.get("result_class") == "negative" or not reconciled:
                                discrepancy = {"source": self.source, "goal_id": goal_id, "action_id": action.action_id,
                                               "route_hash": intervention.route_hash, "result_class": outcome.get("result_class"),
                                               "expected_vs_actual": outcome.get("expected_vs_actual"), "at": at,
                                               "disposition": "discrepancy_visible_not_hidden"}
                                self.ledger.append(self.DISCREPANCY_RECORD, discrepancy)
                                blockers.append(f"outcome discrepancy: {intervention.intervention_id} "
                                                f"({outcome.get('result_class')}; {outcome.get('expected_vs_actual')})"[:200])
                                items.append(self._inform(spec, title="outcome discrepancy", urgency="high", now=at,
                                                          marginal_value=0.85,
                                                          text=f"Move '{intervention.description}' executed but the outcome did not match: "
                                                               f"{outcome.get('expected_vs_actual')}. The goal is blocked until reviewed.",
                                                          evidence_refs=[action.receipt_hash], category="discrepancy"))
                            elif self.retention is not None and outcome.get("result_class") == "positive":
                                self.retention.retain(goal_id=goal_id, outcome_ref=detail["outcome_id"],
                                                      what_worked=[intervention.description],
                                                      assets=[DurableAsset.build(kind="evidence", name=f"receipt:{action.receipt_hash[:19]}",
                                                                                 description=f"verified receipt for {intervention.description}",
                                                                                 evidence_refs=[action.receipt_hash])], now=at)
                        elif action.state == "reconciliation_required":
                            record("unknown", {"action_id": action.action_id, "reasons": action.refusal_reasons})
                            entry["evidence_state"] = "unknown"
                            blockers.append("gate outcome unknown; reconciliation required")
                        else:
                            record("failed", {"action_id": action.action_id, "state": action.state,
                                              "reasons": action.refusal_reasons})
                            entry["evidence_state"] = "failed"
                            blockers.append(f"gate {action.state}: {'; '.join(action.refusal_reasons)[:160]}")
                        executed_this_goal = True
                elif classification.decision in ("PREPARE_FOR_FOUNDER", "ESCALATE"):
                    package = {"source": self.source, "goal_id": goal_id, "intervention": intervention.to_dict(),
                               "classification_id": classification.classification_id, "fix_hash": fix.fix_hash,
                               "reasons": list(classification.reasons), "prepared_at": at,
                               "evidence_refs": list(evidence_refs), "disposition": "prepared_not_executed"}
                    self.ledger.append(self.PREPARED_RECORD, package)
                    record("planned", {"prepared": True})
                    prepared.append({"goal_id": goal_id, "intervention_id": intervention.intervention_id,
                                     "decision": classification.decision})
                    urgency = "high" if classification.decision == "ESCALATE" else "normal"
                    items.append(self._ask_for(spec, intervention, classification, kind="decision", urgency=urgency,
                                               now=at, fix=fix, evidence_refs=evidence_refs))
                    if classification.decision == "ESCALATE":
                        escalated.append({"goal_id": goal_id, "intervention_id": intervention.intervention_id})
                    entry["evidence_state"] = "planned"
                elif classification.decision == "REQUEST_EVIDENCE":
                    record("planned", {"missing": list(classification.missing), "evidence_basis": evidence_basis})
                    blockers.append(f"evidence below floor for {intervention.consequence_class}")
                    deficits.append(self._record_deficit(goal_id, "proof",
                                                         f"{intervention.intervention_id}: evidence below floor for {intervention.consequence_class}", now=at))
                    entry["evidence_state"] = "planned"
                elif classification.decision == "WAIT":
                    blockers.extend(f"capability deficit: {c}" for c in fix.missing_capabilities)
                    entry["evidence_state"] = "planned"
                else:  # ABSTAIN
                    entry["evidence_state"] = "planned"
                decisions.append(entry)
            summary["decisions"] = decisions
            summary["deficits"] = deficits
            # 7b. Personal advancement (section 5): authorized vs observed trajectory, friction, one mature report.
            pending_decisions = [i.to_dict() for i in items if i.goal_id == goal_id and i.kind == "decision"]
            known = {a["item_id"] for a in pending_decisions}
            open_for_goal = [a for a in self.attention.open_asks() if a["goal_id"] == goal_id and a["item_id"] not in known]
            report = self.advancement.assess(goal_id, summary={**summary, "blockers_now": sorted(set(blockers))}, now=at,
                                             open_asks=pending_decisions + open_for_goal,
                                             latest_by_route=self._latest_by_route(goal_id), evidence_refs=evidence_refs)
            if report is not None:
                summary["advancement"] = {"stalled": report["stalled"], "main_friction": report["main_friction"],
                                          "behind_target": [n["node_id"] for n in report["behind_target"]]}
                items.append(self._advancement_item(spec, report, now=at))
            blocked = bool(fix.missing_capabilities) or bool(unmet) or (routing is not None and routing.deficit is not None) or any(
                "evidence below floor" in b or "unknown" in b or "discrepancy" in b or "reconciliation" in b
                or "resource budget" in b for b in blockers)
            self.registry.transition(goal_id, reason="gravity turn processed", now=at,
                                     status="blocked" if blocked else "dormant",
                                     current_state=fix.current_position, active_node_id=fix.active_node_id,
                                     active_gate=fix.active_gate, sbm=fix.sbm, blockers=sorted(set(blockers)),
                                     missing_capabilities=list(fix.missing_capabilities),
                                     missing_relationships=list(fix.missing_relationships), deficits=deficits,
                                     evidence_refs=list(state.evidence_refs))
            processed.append(summary)

        # 8. Protect attention: route asks by leverage, dedupe, batch, respect quiet hours.
        routing: Routing = self.attention.route(items, now=at)
        if hibernating:
            status = "hibernating"
        elif conserving:
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
            experience_surface=self.world.experience_surface(goals=[self.registry.get(g) for g in self.registry.goals()], now=at),
            deliberation="standing_cognition" if self.cognition is not None else "declared_moves",
            deferred=tuple(deferred), derived_signal_ids=tuple(s.signal_id for s in derived))
        self.ledger.append(self.TURN_RECORD, {"source": self.source, "turn": turn.to_dict(), "disposition": "proposal_only"})
        self._sync()
        return turn

    # ------------------------------------------------------------ reconciliation and verification
    def reconcile(self, goal_id: str, *, now: datetime | str,
                  resolutions: Mapping[str, Mapping[str, Any]] | None = None) -> dict[str, Any]:
        """Close open attempts (``attempted``/``unknown``) from the Gate's own ledger events.

        A route the Gate recorded becomes ``executed``; one the Gate refused/denied/expired/revoked/failed
        becomes ``failed``; one the Gate left at ``reconciliation_required`` (or that never reached a terminal
        state) stays open unless an accountable ``resolutions[route_hash]`` of the form
        ``{"state": "executed"|"failed", "reconciled_by": <actor>, "evidence_refs": [...], "note": ...}``
        is supplied, and that resolution is recorded with its author. Nothing is retried here.
        """
        self._sync()
        at = iso(parse_time(now))
        self.registry.get(goal_id)
        resolutions = {k: canonical_copy(dict(v)) for k, v in (resolutions or {}).items()}
        resolved: list[dict[str, Any]] = []
        unresolved: list[str] = []
        for route, item in self._latest_by_route(goal_id).items():
            if item["evidence_state"] not in OPEN_ATTEMPT_STATES:
                continue
            intervention = InterventionSpec.from_dict(item["intervention"])
            proposal_id = item["detail"].get("proposal_id") or self.classifier.proposal_id_for(goal_id, route)
            observed = self._gate_observation(proposal_id)
            new_state: str | None = None
            carried = {k: item["detail"][k] for k in ("routing_decision_id", "routed_mechanisms", "expected_evidence", "attempt")
                       if k in item["detail"]}
            detail: dict[str, Any] = {**carried, "proposal_id": proposal_id, "reconciled_from": "gate_ledger_events"}
            if observed and observed["state"] == "recorded":
                outcome = observed.get("outcome", {})
                new_state = "executed"
                detail.update({"action_id": observed["action_id"], "outcome_id": outcome.get("outcome_id"),
                               "receipt_hash": observed.get("receipt_hash"), "result_class": outcome.get("result_class"),
                               "expected_vs_actual": outcome.get("expected_vs_actual"),
                               "executor_claimed_validation": outcome.get("validation_status")})
            elif observed and observed["state"] in GATE_TERMINAL_FAILED:
                new_state = "failed"
                detail.update({"action_id": observed["action_id"], "state": observed["state"], "reasons": observed["reasons"]})
            elif route in resolutions:
                res = resolutions[route]
                if res.get("state") not in ("executed", "failed"):
                    raise ContractError("a resolution must state executed or failed")
                refs = [require_text("evidence_refs[]", r) for r in res.get("evidence_refs", [])]
                if not refs:
                    raise ContractError("a resolution needs evidence references")
                new_state = res["state"]
                detail = {**carried, "proposal_id": proposal_id, "reconciled_from": "accountable_resolution",
                          "reconciled_by": require_text("reconciled_by", res.get("reconciled_by", "")),
                          "evidence_refs": refs, "note": require_text("note", res.get("note", ""))}
            if new_state is None:
                unresolved.append(route)
                continue
            payload = self._record_intervention(goal_id, intervention, classification_id=item["classification_id"],
                                                decision=item["decision"], evidence_state=new_state, detail=detail, now=at)
            self.ledger.append(self.RECONCILIATION_RECORD, {"source": self.source, "goal_id": goal_id, "route_hash": route,
                                                            "from": item["evidence_state"], "to": new_state,
                                                            "detail": detail, "at": at, "disposition": "reconciled"})
            resolved.append({"route_hash": route, "from": item["evidence_state"], "to": new_state,
                             "intervention_id": intervention.intervention_id})
            if new_state == "executed" and detail.get("receipt_hash"):
                state = self.registry.state(goal_id)
                if detail["receipt_hash"] not in state.evidence_refs:
                    self.registry.transition(goal_id, reason=f"reconciled receipt for {intervention.intervention_id}", now=at,
                                             evidence_refs=list(state.evidence_refs) + [detail["receipt_hash"]])
        state = self.registry.state(goal_id)
        remaining = [b for b in state.blockers if not (
            ("reconciliation" in b or "unknown" in b) and not any(r[7:23] in b for r in unresolved) and
            not (unresolved and "gate outcome unknown" in b))]
        if unresolved:
            remaining = sorted(set(remaining) | {f"reconciliation required: route {r[7:23]} outcome unknown" for r in unresolved})
        if resolved or remaining != list(state.blockers):
            self.registry.transition(goal_id, reason="reconciliation", now=at, blockers=sorted(set(remaining)),
                                     status="blocked" if remaining else ("dormant" if state.status == "blocked" else state.status))
        return {"goal_id": goal_id, "resolved": resolved, "unresolved": unresolved, "at": at}

    def verify_outcome(self, goal_id: str, route_hash: str, *, verifier: str, evidence_refs: Sequence[str], note: str,
                       now: datetime | str, verdict: str = "confirmed") -> dict[str, Any]:
        """``externally_verified`` is earned, never self-certified: an independent verifier cites evidence.

        ``verdict`` is ``confirmed`` (the outcome is what the move claimed) or ``refuted`` (it is not). A
        refuted move stays ``executed``, records a discrepancy and blocks the goal; it is never released for
        re-dispatch. Either verdict calibrates the Competency Compiler's track record for every mechanism the
        move was routed through. Every independence rule is checked before anything is written, and one
        action is verified at most once.
        """
        self._sync()
        at = iso(parse_time(now))
        self.registry.get(goal_id)
        if verdict not in ("confirmed", "refuted"):
            raise ContractError("verdict must be 'confirmed' or 'refuted'")
        verifier = require_text("verifier", verifier)
        refs = [require_text("evidence_refs[]", r) for r in evidence_refs]
        if not refs:
            raise ContractError("external verification needs at least one evidence reference")
        note = require_text("note", note)
        latest = self._latest_by_route(goal_id).get(route_hash)
        if latest is None or latest["evidence_state"] != "executed" or latest["detail"].get("verdict"):
            raise ContractError("only an executed, not yet verified move can be externally verified")
        action_id = latest["detail"].get("action_id")
        if any(r.payload.get("action_id") == action_id for r in self.ledger.by_type(self.VERIFICATION_RECORD)):
            raise ContractError("this action has already been verified; one verification per action")
        recorded_by = None
        for record in self.ledger.by_type("outcome"):
            if record.payload.get("action_ref") == action_id:
                recorded_by = record.payload.get("recorded_by")
        if verifier in (self.classifier.actor, recorded_by, self.source):
            raise ContractError("verification must be independent of the actor that executed the move")
        mechanisms = tuple(latest["detail"].get("routed_mechanisms", ()))
        decision_id = latest["detail"].get("routing_decision_id")
        if mechanisms and self.competency is not None:
            self.competency.check_verifier(verifier, mechanisms)
        intervention = InterventionSpec.from_dict(latest["intervention"])
        verification = self.ledger.append(self.VERIFICATION_RECORD, {
            "source": self.source, "goal_id": goal_id, "route_hash": route_hash, "action_id": action_id,
            "verifier": verifier, "verdict": verdict, "evidence_refs": refs, "note": note, "at": at,
            "routing_decision_id": decision_id, "routed_mechanisms": list(mechanisms),
            "disposition": "externally_verified_by_independent_party" if verdict == "confirmed"
                           else "refuted_by_independent_party"})
        detail = {**latest["detail"], "verifier": verifier, "verdict": verdict, "verification_evidence_refs": refs,
                  "verification_hash": verification.hash, "note": note, "verified_at": at}
        calibration: list[dict[str, Any]] = []
        if mechanisms and decision_id and self.competency is not None:
            calibration = self.competency.record_outcomes(decision_id, mechanisms, correct=verdict == "confirmed",
                                                          evidence_ref=verification.hash, verified_by=verifier)
            detail["calibration"] = calibration
        state = self.registry.state(goal_id)
        if verdict == "confirmed":
            payload = self._record_intervention(goal_id, intervention, classification_id=latest["classification_id"],
                                                decision=latest["decision"], evidence_state="externally_verified",
                                                detail=detail, now=at)
            self.registry.transition(goal_id, reason=f"outcome externally verified by {verifier}", now=at,
                                     evidence_refs=list(dict.fromkeys(list(state.evidence_refs) + refs)))
        else:
            payload = self._record_intervention(goal_id, intervention, classification_id=latest["classification_id"],
                                                decision=latest["decision"], evidence_state="executed",
                                                detail=detail, now=at)
            self.ledger.append(self.DISCREPANCY_RECORD, {
                "source": self.source, "goal_id": goal_id, "action_id": action_id, "route_hash": route_hash,
                "result_class": "refuted_by_verifier", "expected_vs_actual": note, "at": at,
                "disposition": "discrepancy_visible_not_hidden"})
            self.registry.transition(goal_id, reason=f"outcome refuted by {verifier}", now=at, status="blocked",
                                     blockers=sorted(set(state.blockers) | {
                                         f"outcome discrepancy: {intervention.intervention_id} refuted by {verifier}"}),
                                     evidence_refs=list(dict.fromkeys(list(state.evidence_refs) + refs)))
        return payload

    def propose_attach(self, goal_id: str, qualification: Mapping[str, Any], *, now: datetime | str) -> Routing:
        """Route the one founder decision a passed qualification needs (nothing attaches until it is accepted)."""
        if not qualification.get("passed"):
            raise ContractError("only a passed qualification can be proposed for attachment")
        return self.attention.route([self.acquisition.attach_item(goal_id, qualification, now=iso(parse_time(now)))], now=now)

    # ------------------------------------------------------------ founder surface
    def founder_answer(self, item_id: str, *, decision: str, actor: str, note: str, now: datetime | str) -> dict[str, Any]:
        """Record the answer. For a human-only gate, an accept or refuse also becomes typed gate evidence
        (method ``human_decision`` / ``legal_determination``), the only path by which such evidence exists.
        Founder identity here is declared lineage, not authentication (SR001 G6); trust stays ``attributed``."""
        item = next((a for a in self.attention.open_asks() if a["item_id"] == item_id), None)
        answer = self.attention.answer(item_id, decision=decision, actor=actor, note=note, now=now)
        attach = (item or {}).get("attach_on_accept")
        if attach and decision == "accept":
            answer = {**answer, "attached": self.acquisition.attach(attach["qualification_hash"], actor=actor, now=now)}
        gate = (item or {}).get("evidence_on_accept")
        if gate and decision in ("accept", "refuse"):
            at = iso(parse_time(now))
            answer_hash = next((r.hash for r in reversed(self.ledger.by_type(self.attention.ANSWER_RECORD))
                                if r.payload["item_id"] == item_id), None)
            subject, attribute = gate["sbm"].split(".", 1)
            target = gate["value"]
            value = target if decision == "accept" else (not target if isinstance(target, bool) else None)
            signal = SignalEnvelope.build(
                source="founder://answers", source_event_id=f"{item_id}:{decision}", observed_at=at,
                payload={"observations": [{"subject": subject, "attribute": attribute, "value": value,
                                           "confidence": 1.0, "method": gate["method"]}]},
                evidence_refs=tuple(r for r in (answer_hash,) if r), trust_level="attributed")
            self.world.integrate(signal, now=at, goal_relevance={item["goal_id"]: 1.0},
                                 context={"founder_answer": item_id, "routing_decision_id": gate.get("routing_decision_id")},
                                 attention=[item["goal_id"]], allow_human_methods=True)
            answer = {**answer, "gate_evidence": {"sbm": gate["sbm"], "value": value, "method": gate["method"],
                                                  "signal_id": signal.signal_id}}
        return answer

    def work_to_first_actionable(self, goal_id: str) -> dict[str, Any]:
        """How much work a goal needed before its first actionable move (execute/prepare/escalate).

        Counts gravity turns that processed the goal, classifications made, and deficit records written,
        up to and including the turn carrying the first actionable decision. Lower means cheaper.
        """
        turns = 0
        classifications = 0
        first_actionable_turn: int | None = None
        for record in self.ledger.by_type(self.TURN_RECORD):
            for processed in record.payload["turn"]["processed"]:
                if processed["goal_id"] != goal_id:
                    continue
                turns += 1
                classifications += len(processed.get("decisions", []))
                if first_actionable_turn is None and any(d["decision"] in ACTIONABLE for d in processed.get("decisions", [])):
                    first_actionable_turn = turns
            if first_actionable_turn is not None:
                break
        deficits = sum(1 for r in self.ledger.by_type(self.DEFICIT_CLASS_RECORD) if r.payload["goal_id"] == goal_id)
        return {"goal_id": goal_id, "turns": turns, "classifications": classifications, "deficits": deficits,
                "first_actionable_turn": first_actionable_turn,
                "work_units": turns + classifications + deficits}

    def measures(self, *, now: datetime | str | None = None) -> dict[str, Any]:
        """Directive section 19: engineer and measure intelligence, agency, persistent identity and the
        experiential surface separately; subjective consciousness stays unresolved and unmeasured."""
        self._sync()
        ok, chain = self.ledger.verify_chain()
        decisions: dict[str, int] = {}
        for item in self._interventions:
            decisions[item["decision"]] = decisions.get(item["decision"], 0) + 1
        latest_states = [i["evidence_state"] for g in self.registry.goals() for i in self._latest_by_route(g).values()]
        executed = sum(1 for s in latest_states if s in DONE_STATES)
        verified = sum(1 for s in latest_states if s == "externally_verified")
        attempted = sum(1 for i in self._interventions if i["evidence_state"] == "attempted")
        open_attempts = sum(1 for s in latest_states if s in OPEN_ATTEMPT_STATES)
        return {
            "persistent_identity": {"goals": len(self.registry.goals()), "ledger_head": self.ledger.head,
                                    "chain_intact": ok, "chain_detail": chain, "turns": len(self._turns)},
            "agency": {"decisions": decisions, "executed_under_grant": executed, "externally_verified": verified,
                       "attempted": attempted, "open_attempts": open_attempts,
                       "executed_fraction_of_attempts": (executed / attempted) if attempted else None,
                       "note": "execution only through the Consequence Gate under caller-supplied grants"},
            "intelligence": {"status": "not measured here", "requires": "CausalMemory.calibrate over predicted vs realized "
                             "outcomes of real moves; institutional_learning currently reports " +
                             str(len(self.memory.institutional_learning())) + " action class(es)"},
            "experiential_surface": self.world.experience_surface(
                goals=[self.registry.get(g) for g in self.registry.goals()], now=now),
            "competency": self._competency_measures(),
            "founder_burden": self._founder_burden(),
            "subjective_consciousness": "unresolved; not measured; not claimed",
        }

    def _founder_burden(self) -> dict[str, Any]:
        """Section 30: GREG becomes more capable while Alfonso becomes less operationally burdened."""
        asks = [r.payload for r in self.ledger.by_type(self.attention.ASK_RECORD)]
        answers = [r.payload for r in self.ledger.by_type(self.attention.ANSWER_RECORD)]
        routed_at = {a["item"]["item_id"]: a["routed_at"] for a in asks}
        latencies = [(parse_time(a["answered_at"]) - parse_time(routed_at[a["item_id"]])).total_seconds()
                     for a in answers if a["item_id"] in routed_at]
        done = sum(1 for g in self.registry.goals() for i in self._latest_by_route(g).values()
                   if i["evidence_state"] in DONE_STATES)
        turns = max(1, len(self._turns))
        return {"immediate_asks": sum(1 for a in asks if a["lane"] == "immediate"),
                "batched_asks": sum(1 for a in asks if a["lane"] == "batched"),
                "immediate_asks_per_turn": round(sum(1 for a in asks if a["lane"] == "immediate") / turns, 4),
                "asks_per_completed_move": round(len(asks) / done, 4) if done else None,
                "answers": len(answers),
                "mean_answer_latency_seconds": (sum(latencies) / len(latencies)) if latencies else None,
                "note": "lower is better at constant or rising completed work"}

    def _competency_measures(self) -> dict[str, Any]:
        """How the Competency Compiler is being used: routed gates, deficits, human gates, verified track records."""
        routed = deficits = human = 0
        for turn in self._turns.values():
            for p in turn.processed:
                r = p.get("routing") or {}
                if r.get("decision_id"):
                    routed += 1
                    deficits += 1 if r.get("deficit") else 0
                    human += 1 if r.get("human_escalation") else 0
        outcomes = [r.payload for r in self.ledger.by_type("event") if r.payload.get("type") == "capabilities.routing_outcome"]
        return {"attached": self.competency is not None, "gate_routings": routed, "epistemic_deficits": deficits,
                "human_only_gates": human, "verified_outcomes": len(outcomes),
                "unrouted_gates_this_process": self.competency.unrouted_gates if self.competency else None,
                "note": "calibration counts only independently verified, evidence-referenced outcomes"}

    def status(self, goal_id: str, *, now: datetime | str) -> dict[str, Any]:
        """The founder-facing compression of section 27: where things stand, in one read."""
        self._sync()
        spec = self.registry.get(goal_id)
        state = self.registry.state(goal_id)
        fix = self.gps.fix(spec, state, now=now, record=False)
        open_asks = [a for a in self.attention.open_asks() if a["goal_id"] == goal_id]
        prepared = [r.payload for r in self.ledger.by_type(self.PREPARED_RECORD) if r.payload["goal_id"] == goal_id]
        latest = self._latest_by_route(goal_id)
        evidence_state = {route: item["evidence_state"] for route, item in latest.items()}
        latest_decision = {route: d for (g, route), d in self._decisions.items() if g == goal_id}
        autonomous, waiting = [], []
        for raw in fix.next_interventions:
            decision = latest_decision.get(raw["route_hash"])
            if state.status == "paused":
                waiting.append({"intervention_id": raw["intervention_id"], "why": "goal paused by founder"})
            elif decision in (None, "EXECUTE_AUTONOMOUSLY"):
                autonomous.append(raw)
            elif decision in ("PREPARE_FOR_FOUNDER", "ESCALATE"):
                waiting.append({"intervention_id": raw["intervention_id"], "why": "founder decision"})
            else:
                waiting.append({"intervention_id": raw["intervention_id"], "why": decision})
        return {
            "goal_id": goal_id, "founder_intent": spec.founder_intent, "desired_state": spec.desired_state,
            "status": state.status, "priority": self.registry.effective_priority(goal_id),
            "current_position": fix.current_position, "critical_assumptions": list(spec.assumptions),
            "active_node": fix.active_node_id, "active_gate": fix.active_gate,
            "single_bottleneck_metric": fix.sbm, "exit_evidence": list(fix.exit_evidence),
            "relevant_environmental_signals": [e.signal_id for e in self.world.experiences() if goal_id in e.goal_relevance],
            "available_capabilities": [c for n in spec.plan for c in n.requires_capabilities if c not in fix.missing_capabilities],
            "missing_capabilities": list(fix.missing_capabilities), "missing_relationships": list(fix.missing_relationships),
            "deficits": list(state.deficits), "route_changed": fix.route_changed,
            "next_autonomous_work": autonomous, "waiting_work": waiting,
            "prepared_work": [p["intervention"]["intervention_id"] for p in prepared],
            "founder_required_decisions": [a["item_id"] for a in open_asks],
            "evidence_state": evidence_state, "blockers": list(state.blockers),
            "review_trigger": f"relevant signal, favorable intersection, or every {spec.review_cadence_seconds} seconds",
            "drift": self.drift_report(goal_id)["drift"],
            "trajectory": self._trajectory_status(goal_id, now=now),
            "competency": self._latest_routing(goal_id),
            "gate_controller": self._gate_controller(spec, fix, goal_id),
            "changed_since_last_assessment": self._changed_since_last_fix(goal_id),
            "threats": self._latest_threats(goal_id),
            "retained_assets": [a for r in self.ledger.by_type("egregore.asset_retained")
                                if r.payload["retention"]["goal_id"] == goal_id for a in r.payload["retention"]["assets"]],
            "deliberation": "standing_cognition" if self.cognition is not None else "declared_moves",
            "execution_authority": "none",
        }

    def _gate_controller(self, spec: GoalSpec, fix: GPSFix, goal_id: str) -> dict[str, Any] | None:
        """Section 3, 'what currently controls that gate?': the metric, the evidence it needs, and who can supply it."""
        if fix.active_node_id is None:
            return None
        node = spec.node(fix.active_node_id)
        routing = self._latest_routing(goal_id) or {}
        from .gps import admissible_evidence
        needed = admissible_evidence(node.problem_class)
        return {"metric": node.sbm, "target": node.sbm_target, "direction": node.sbm_direction,
                "problem_class": node.problem_class, "evidence_needed": sorted(needed) if needed else "any trusted observation",
                "supplied_by": (list(routing.get("human_escalation", [])) and ["Alfonso (" + ", ".join(routing["human_escalation"]) + ")"])
                               or list(routing.get("selected", [])) or ["an observation from a trusted sensor"],
                "requires_capabilities": list(node.requires_capabilities),
                "requires_relationships": list(node.requires_relationships)}

    def _changed_since_last_fix(self, goal_id: str) -> dict[str, Any]:
        """Section 3, 'what changed in reality since the previous assessment?': diff of the last two GPS fixes."""
        fixes = [r.payload["fix"] for r in self.ledger.by_type(self.gps.GPS_RECORD) if r.payload["fix"]["goal_id"] == goal_id]
        if len(fixes) < 2:
            return {"assessments": len(fixes), "changes": {}}
        a, b = fixes[-2], fixes[-1]
        changes = {k: {"before": a["current_position"].get(k), "after": v}
                   for k, v in b["current_position"].items() if a["current_position"].get(k) != v}
        if a["active_node_id"] != b["active_node_id"]:
            changes["active_node"] = {"before": a["active_node_id"], "after": b["active_node_id"]}
        return {"assessments": len(fixes), "since": a["fixed_at"], "changes": changes}

    def _latest_threats(self, goal_id: str) -> list[str]:
        for turn in sorted(self._turns.values(), key=lambda x: x.at, reverse=True):
            for p in turn.processed:
                if p["goal_id"] == goal_id and "intersection" in p:
                    return list(p["intersection"].get("threats", []))
        return []

    def _latest_routing(self, goal_id: str) -> dict[str, Any] | None:
        """The Competency Compiler's last view of this goal's gate (read-only: status never routes)."""
        for turn in sorted(self._turns.values(), key=lambda x: x.at, reverse=True):
            for p in turn.processed:
                if p["goal_id"] == goal_id and "routing" in p:
                    return p["routing"]
        return None

    def _trajectory_status(self, goal_id: str, *, now: datetime | str) -> dict[str, Any]:
        points = self.advancement.trajectory(goal_id)
        start = self.advancement.stall_start(points) if points else 0
        reports = [r.payload for r in self.ledger.by_type(self.advancement.REPORT_RECORD) if r.payload["goal_id"] == goal_id]
        return {"observed_points": len(points), "reviews_without_progress": len(points) - start if points else 0,
                "behind_target": self.advancement.behind_target(goal_id, now=now),
                "last_report": ({"reported_at": reports[-1]["reported_at"], "main_friction": reports[-1]["main_friction"]}
                                if reports else None)}
