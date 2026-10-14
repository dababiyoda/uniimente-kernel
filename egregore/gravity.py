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

Body mode. On a GREG body ledger (one carrying ``greg.founder.enrolled``), or
when constructed with ``body_mode=True``, the body owns authority: founder
commands are Ed25519-signed, missions execute through the AuthorityOffice and
its Gate, and founder asks have one path. There the loop refuses any gate,
executor or grant in ``turn`` (it can wake, backcast, classify, prepare and
route attention, never execute), its attention store writes no founder ask or
answer of its own, unhydratable goal records are quarantined instead of
faulting every turn, and a goal with no world evidence gets confidence 0
labelled ``no_world_evidence`` instead of the caller's attestation.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Mapping, Sequence

from .attention import (AttentionItem, AttentionPolicy, FounderAttentionRouter, LedgerAttentionStore,
                        MemoryAttentionStore, Routing)
from .cognition_seam import GoalProposer, cadence_signal, candidate_to_intervention, goal_context
from .contracts import ContractError, IntegrityConflict, SignalEnvelope, canonical_copy, digest, require_text
from .experience import WorldModel
from .goals import CONSEQUENCE_CLASSES, GoalRegistry, GoalSpec, InterventionSpec, body_ledger_scan, iso, parse_time
from .gps import BackcastGPSAdapter, GPSFix
from .intersections import FavorableIntersectionDetector, IntersectionReport
from .interventions import Classification, InterventionClassifier
from .relevance import GoalRelevanceRouter
from .resources import ResourceExhausted, ResourceGovernor, ResourceMode
from .retention import AsymmetryRetention, DurableAsset

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
    wake_refused: tuple[dict[str, Any], ...] = ()   # goals whose wake the registry refused (isolated, recorded)

    @property
    def execution_authority(self) -> str:
        return "none"

    def to_dict(self) -> dict[str, Any]:
        out = {
            "turn_id": self.turn_id, "trigger_id": self.trigger_id, "request_hash": self.request_hash,
            "status": self.status, "at": self.at, "signal_ids": list(self.signal_ids), "woken": list(self.woken),
            "processed": list(self.processed), "executed": list(self.executed), "prepared": list(self.prepared),
            "escalated": list(self.escalated), "routing": self.routing, "resource_snapshot": self.resource_snapshot,
            "experience_surface": self.experience_surface, "deliberation": self.deliberation,
            "deferred": list(self.deferred), "execution_authority": "none"}
        if self.wake_refused:   # absent when empty: earlier turn records keep their exact shape
            out["wake_refused"] = list(self.wake_refused)
        return canonical_copy(out)

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
                   wake_refused=tuple(value.get("wake_refused", ())))


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
    WAKE_REFUSED_RECORD = "egregore.goal_wake_refused"

    def __init__(self, *, ledger: Any, compiled: Any, passports: Any, actor: str, legal_principal: str,
                 genomes: Any = None, cognition: Any = None, memory: Any = None,
                 attention_policy: AttentionPolicy | None = None,
                 source: str = "spiffe://uniimente.internal/egregore/goal-gravity",
                 body_mode: bool = False, attention_store: Any = None):
        if not hasattr(ledger, "append") or not hasattr(ledger, "by_type") or not hasattr(ledger, "records"):
            raise ContractError("ledger must provide append(), by_type() and records")
        self.ledger = ledger
        # Body mode is decided by the ledger as well as the constructor: a loop on a GREG body ledger is
        # hosted whatever its caller asked for, so no caller can hand it a gate, an executor or a grant.
        hosted, self._host_scanned = body_ledger_scan(ledger)
        self._body_mode = bool(body_mode) or hosted
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
        self.registry = GoalRegistry(ledger=ledger, source=source,
                                     quarantine_unhydratable=True if self._body_mode else None)
        self.world = WorldModel(ledger=ledger, source=source)
        self.genomes = genomes
        self.router = GoalRelevanceRouter(self.registry)
        self.gps = BackcastGPSAdapter(ledger=ledger, world=self.world, genomes=genomes, memory=memory, source=source)
        self.classifier = InterventionClassifier(ledger=ledger, registry=self.registry, compiled=compiled,
                                                 passports=passports, actor=actor, legal_principal=legal_principal,
                                                 source=source)
        self.detector = FavorableIntersectionDetector(ledger=ledger, world=self.world, source=source)
        self.retention = AsymmetryRetention(ledger=ledger, registry=self.registry, genomes=genomes, source=source) if genomes is not None else None
        if attention_store is None and self._body_mode:
            attention_store = MemoryAttentionStore()
        self.attention = FounderAttentionRouter(ledger=ledger, registry=self.registry, policy=attention_policy,
                                                source=source, store=attention_store)
        self._turns: dict[str, GravityTurn] = {}
        self._interventions: list[dict[str, Any]] = []
        self._decisions: dict[tuple[str, str], str] = {}   # (goal_id, route_hash) -> latest classification
        self._folded = 0
        self._sync()

    @property
    def execution_authority(self) -> str:
        return "none"

    @property
    def body_mode(self) -> bool:
        """Hosted on a GREG body (or constructed so): proposal-only, whatever a caller passes to ``turn``."""
        if not self._body_mode:
            hosted, self._host_scanned = body_ledger_scan(self.ledger, start=self._host_scanned)
            if hosted:   # a founder enrolled after construction: hosted from now on
                self._body_mode = True
                self.registry.quarantine_unhydratable = True
                if isinstance(self.attention.store, LedgerAttentionStore):
                    inert = MemoryAttentionStore()
                    inert._open = dict(self.attention.store._open)   # keep dedupe of what was already routed
                    self.attention.store = inert
        return self._body_mode

    # ------------------------------------------------------------ ledger projection
    def _sync(self) -> None:
        """Fold ledger records appended since the last fold (by this loop, another loop, the Gate, retention)."""
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
        if self._body_mode:   # refreshed by ``turn`` through the body_mode property
            # Hosted: nothing observed for this goal means no evidence, whatever the caller attests.
            return all_refs, 0.0, "no_world_evidence"
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
            route_hash=intervention.route_hash, tactic=intervention.tactic or None)

    def _inform(self, spec: GoalSpec, *, title: str, text: str, urgency: str, evidence_refs: Sequence[str],
                now: str, marginal_value: float, category: str = "information") -> AttentionItem:
        """'Alfonso should know': information items request nothing and always cost nothing."""
        return AttentionItem.build(
            goal_id=spec.goal_id, kind="information", urgency=urgency, marginal_value=min(1.0, marginal_value),
            title=f"{spec.desired_state[:60]}: {title}"[:160], question=text,
            options=({"label": "noted", "cost": "none"}, {"label": "raise this goal's priority", "cost": "none"}),
            recommendation="no action needed; GREG continues within its authority",
            evidence_refs=tuple(evidence_refs[:5]), effort_estimate="none", category=category, created_at=now)

    def _inform_intersection(self, spec: GoalSpec, report: IntersectionReport, *, now: str) -> AttentionItem:
        return self._inform(
            spec, title="favorable intersection", urgency="low", now=now,
            marginal_value=0.2 + 0.1 * len(report.domains),
            text=f"{len(report.satisfied)} weak signals across {', '.join(report.domains)} converged "
                 f"(score {report.score:.2f} vs threshold {report.threshold:.2f}). No action is requested.",
            evidence_refs=[s["signal_id"] for s in report.satisfied])

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
        if self.body_mode and (gate is not None or executor is not None or grants):
            raise ContractError("a body-hosted Goal Gravity loop takes no gate, executor or grants: the body's "
                                "missions execute through its AuthorityOffice and Consequence Gate")
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

        # 1. Sense -> Experience: every signal becomes a provenance-backed experience.
        wake_requests: dict[str, list[str]] = {}
        relevant_signals: dict[str, list[str]] = {}
        touched_keys: set[str] = set()
        for signal in ordered_signals:
            if self.cognition is not None:
                self.cognition.ingest(signal)
            observations = self.world.observations_from_signal(signal)
            touched_keys.update(o.key for o in observations)
            verdicts = self.router.route(signal, observations=observations)
            woke_here = [g for g, v in verdicts.items() if v.wake]
            self.world.integrate(signal, now=at, goal_relevance={g: v.score for g, v in verdicts.items()},
                                 context={"trigger_id": trigger_id}, attention=woke_here)
            for goal_id, verdict in verdicts.items():
                relevant_signals.setdefault(goal_id, []).append(signal.signal_id)
                if verdict.wake:
                    wake_requests.setdefault(goal_id, []).append(signal.signal_id)
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
        wake_refused: list[dict[str, Any]] = []
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
                    try:
                        self.registry.wake(goal_id, reason=reason, now=at, signal_ids=signal_ids)
                    except ContractError as exc:   # one goal's refusal never faults the turn for the others
                        refused = {"goal_id": goal_id, "reason": reason, "signal_ids": list(signal_ids),
                                   "error": f"{type(exc).__name__}: {exc}"[:300]}
                        self.ledger.append(self.WAKE_REFUSED_RECORD, {"source": self.source, "trigger_id": trigger_id,
                                                                      **refused, "at": at,
                                                                      "disposition": "not_woken_retained"})
                        wake_refused.append(refused)
                        continue
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
                    items.append(self._inform_intersection(spec, report, now=at))
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
            for dep in unmet:
                deficits.append(self._record_deficit(goal_id, "proof", f"dependency unmet: {dep}", now=at))
                blockers.append(f"dependency unmet: {dep}")
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
                    unmet_dependencies=unmet)
                entry = {"intervention_id": intervention.intervention_id, "decision": classification.decision,
                         "reasons": list(classification.reasons), "selected_by_deliberation": selected,
                         "evidence_confidence": confidence, "evidence_basis": evidence_basis}
                record = lambda evidence_state, detail=None: self._record_intervention(  # noqa: E731
                    goal_id, intervention, classification_id=classification.classification_id,
                    decision=classification.decision, evidence_state=evidence_state, detail=detail, now=at)
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
                            executed.append({"goal_id": goal_id, **detail, "evidence_state": "executed"})
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
            blocked = bool(fix.missing_capabilities) or bool(unmet) or any(
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
            deferred=tuple(deferred), wake_refused=tuple(wake_refused))
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
            detail: dict[str, Any] = {"proposal_id": proposal_id, "reconciled_from": "gate_ledger_events"}
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
                detail = {"proposal_id": proposal_id, "reconciled_from": "accountable_resolution",
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
                       now: datetime | str) -> dict[str, Any]:
        """``externally_verified`` is earned, never self-certified: an independent verifier cites evidence."""
        self._sync()
        at = iso(parse_time(now))
        self.registry.get(goal_id)
        verifier = require_text("verifier", verifier)
        refs = [require_text("evidence_refs[]", r) for r in evidence_refs]
        if not refs:
            raise ContractError("external verification needs at least one evidence reference")
        latest = self._latest_by_route(goal_id).get(route_hash)
        if latest is None or latest["evidence_state"] != "executed":
            raise ContractError("only an executed move can be externally verified")
        recorded_by = None
        action_id = latest["detail"].get("action_id")
        for record in self.ledger.by_type("outcome"):
            if record.payload.get("action_ref") == action_id:
                recorded_by = record.payload.get("recorded_by")
        if verifier in (self.classifier.actor, recorded_by, self.source):
            raise ContractError("verification must be independent of the actor that executed the move")
        intervention = InterventionSpec.from_dict(latest["intervention"])
        detail = {**latest["detail"], "verifier": verifier, "verification_evidence_refs": refs,
                  "note": require_text("note", note), "verified_at": at}
        payload = self._record_intervention(goal_id, intervention, classification_id=latest["classification_id"],
                                            decision=latest["decision"], evidence_state="externally_verified",
                                            detail=detail, now=at)
        self.ledger.append(self.VERIFICATION_RECORD, {"source": self.source, "goal_id": goal_id, "route_hash": route_hash,
                                                      "action_id": action_id, "verifier": verifier, "evidence_refs": refs,
                                                      "at": at, "disposition": "externally_verified_by_independent_party"})
        state = self.registry.state(goal_id)
        self.registry.transition(goal_id, reason=f"outcome externally verified by {verifier}", now=at,
                                 evidence_refs=list(dict.fromkeys(list(state.evidence_refs) + refs)))
        return payload

    # ------------------------------------------------------------ founder surface
    def founder_answer(self, item_id: str, *, decision: str, actor: str, note: str, now: datetime | str) -> dict[str, Any]:
        return self.attention.answer(item_id, decision=decision, actor=actor, note=note, now=now)

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
            "subjective_consciousness": "unresolved; not measured; not claimed",
        }

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
            "deliberation": "standing_cognition" if self.cognition is not None else "declared_moves",
            "execution_authority": "none",
        }
