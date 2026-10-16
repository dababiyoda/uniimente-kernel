"""Persistent Goal Registry with wake/sleep state (Goal Gravity target A + C).

An authorized goal is a durable attractor: it survives process restarts,
sleeps at zero model cost, and wakes from relevant evidence or its review
cadence. Every record here is hydrated from the Evidence Ledger, following
the same restart-safe pattern as ``StandingCognitionRuntime``.

Authority note. A goal carries ``authority`` as *declared lineage*: who
authorized it and the evidence reference for that authorization. Recording
a goal does not authenticate Alfonso, does not create a grant, and does not
let the registry execute anything. Consequential effects still require the
canonical Consequence Gate with a pre-existing grant.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Sequence

from .contract_check import validate_record
from .contracts import (
    ContractError,
    IntegrityConflict,
    canonical_copy,
    digest,
    require_text,
)

GOAL_STATUSES = ("dormant", "awake", "blocked", "paused", "completed", "revoked", "superseded")
DEFICIT_CLASSES = ("capability", "resource", "relationship", "proof")
PRIORITIES = (1, 2, 3, 4, 5)
CONSEQUENCE_CLASSES = ("read_only", "internal_write", "external_contact", "financial", "irreversible")
DIRECTIONS = ("gte", "lte", "eq")
WAKE_KINDS = ("subject", "tag", "domain", "metric")
PREFERENCE_KINDS = (
    "stop_pushing",        # value: bool
    "change_goal",         # value: str (note; the spec itself is immutable, a new goal supersedes)
    "lower_priority",      # value: int 1..5
    "never_use_tactic",    # value: tactic label
    "do_not_monitor",      # value: domain
    "ask_before",          # value: consequence class or action class
    "forget_route",        # value: route hash
    "revoke_capability",   # value: capability name@version
)


class GoalError(ContractError):
    """A goal record is malformed or a transition is not allowed."""


def parse_time(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise GoalError("timestamps must be timezone-aware")
        return value.astimezone(timezone.utc)
    text = require_text("timestamp", value)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise GoalError(f"invalid timestamp {text!r}") from exc
    if parsed.tzinfo is None:
        raise GoalError("timestamps must carry a timezone")
    return parsed.astimezone(timezone.utc)


def iso(value: datetime) -> str:
    return parse_time(value).isoformat().replace("+00:00", "Z")


def _tuple_of_text(name: str, values: Sequence[str]) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise GoalError(f"{name} must be a sequence of strings")
    return tuple(require_text(f"{name}[]", v) for v in values)


def _number(name: str, value: Any, *, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise GoalError(f"{name} must be numeric")
    number = float(value)
    if number != number or number in (float("inf"), float("-inf")):
        raise GoalError(f"{name} must be finite")
    if minimum is not None and number < minimum:
        raise GoalError(f"{name} must be >= {minimum}")
    return number


@dataclass(frozen=True)
class WakeCondition:
    """One reason a dormant goal may wake. Weights add toward ``wake_threshold``."""

    kind: str
    match: str
    weight: float = 1.0
    direction: str | None = None
    threshold: float | None = None

    @classmethod
    def build(cls, *, kind: str, match: str, weight: float = 1.0,
              direction: str | None = None, threshold: float | None = None) -> "WakeCondition":
        kind = require_text("kind", kind)
        if kind not in WAKE_KINDS:
            raise GoalError(f"unknown wake condition kind {kind!r}")
        match = require_text("match", match)
        weight = _number("weight", weight, minimum=0.0)
        if kind == "metric":
            if direction not in DIRECTIONS or threshold is None:
                raise GoalError("metric wake conditions need a direction and threshold")
            threshold = _number("threshold", threshold)
        return cls(kind=kind, match=match, weight=weight, direction=direction, threshold=threshold)

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "match": self.match, "weight": self.weight,
                "direction": self.direction, "threshold": self.threshold}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "WakeCondition":
        return cls.build(kind=value["kind"], match=value["match"], weight=value.get("weight", 1.0),
                         direction=value.get("direction"), threshold=value.get("threshold"))


@dataclass(frozen=True)
class InterventionSpec:
    """A possible next move. It is a description; it carries no authority."""

    intervention_id: str
    description: str
    action_class: str
    requested_capability: str
    consequence_class: str
    target: str
    expected_outcome: str
    payload: dict[str, Any]
    estimated_cost_usd: float = 0.0
    reversible: bool = True
    tactic: str = ""

    @classmethod
    def build(cls, **kw: Any) -> "InterventionSpec":
        clean = {
            "intervention_id": require_text("intervention_id", kw["intervention_id"]),
            "description": require_text("description", kw["description"]),
            "action_class": require_text("action_class", kw["action_class"]),
            "requested_capability": require_text("requested_capability", kw["requested_capability"]),
            "consequence_class": require_text("consequence_class", kw["consequence_class"]),
            "target": require_text("target", kw["target"]),
            "expected_outcome": require_text("expected_outcome", kw["expected_outcome"]),
            "payload": canonical_copy(dict(kw.get("payload", {}))),
            "estimated_cost_usd": _number("estimated_cost_usd", kw.get("estimated_cost_usd", 0.0), minimum=0.0),
            "reversible": bool(kw.get("reversible", True)),
            "tactic": str(kw.get("tactic", "") or ""),
        }
        if clean["consequence_class"] not in CONSEQUENCE_CLASSES:
            raise GoalError(f"unknown consequence class {clean['consequence_class']!r}")
        return cls(**clean)

    @property
    def route_hash(self) -> str:
        """Identity of the tactic as proposed. A changed route has a new hash."""
        return digest({"kind": "egregore-route", "action_class": self.action_class,
                       "requested_capability": self.requested_capability, "target": self.target,
                       "payload": self.payload, "tactic": self.tactic})

    def to_dict(self) -> dict[str, Any]:
        return {"intervention_id": self.intervention_id, "description": self.description,
                "action_class": self.action_class, "requested_capability": self.requested_capability,
                "consequence_class": self.consequence_class, "target": self.target,
                "expected_outcome": self.expected_outcome, "payload": canonical_copy(self.payload),
                "estimated_cost_usd": self.estimated_cost_usd, "reversible": self.reversible,
                "tactic": self.tactic, "route_hash": self.route_hash}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "InterventionSpec":
        fields = {k: v for k, v in value.items() if k != "route_hash"}
        return cls.build(**fields)


@dataclass(frozen=True)
class PlanNode:
    """One backcast state that must become true, with the gate that controls it."""

    node_id: str
    outcome: str
    gate: str
    sbm: str
    sbm_direction: str
    sbm_target: float | bool
    exit_evidence: tuple[str, ...]
    interventions: tuple[InterventionSpec, ...]
    requires_capabilities: tuple[str, ...] = ()
    requires_relationships: tuple[str, ...] = ()

    @classmethod
    def build(cls, *, node_id: str, outcome: str, gate: str, sbm: str, sbm_direction: str,
              sbm_target: float | bool, exit_evidence: Sequence[str] = (),
              interventions: Sequence[InterventionSpec] = (),
              requires_capabilities: Sequence[str] = (),
              requires_relationships: Sequence[str] = ()) -> "PlanNode":
        if sbm_direction not in DIRECTIONS:
            raise GoalError(f"unknown SBM direction {sbm_direction!r}")
        if isinstance(sbm_target, bool):
            if sbm_direction != "eq":
                raise GoalError("boolean SBM targets must use eq")
        else:
            sbm_target = _number("sbm_target", sbm_target)
        specs = tuple(interventions)
        if not all(isinstance(i, InterventionSpec) for i in specs):
            raise GoalError("interventions must be InterventionSpec instances")
        ids = [i.intervention_id for i in specs]
        if len(ids) != len(set(ids)):
            raise GoalError("intervention ids must be unique within a node")
        return cls(node_id=require_text("node_id", node_id), outcome=require_text("outcome", outcome),
                   gate=require_text("gate", gate), sbm=require_text("sbm", sbm),
                   sbm_direction=sbm_direction, sbm_target=sbm_target,
                   exit_evidence=_tuple_of_text("exit_evidence", exit_evidence), interventions=specs,
                   requires_capabilities=_tuple_of_text("requires_capabilities", requires_capabilities),
                   requires_relationships=_tuple_of_text("requires_relationships", requires_relationships))

    def to_dict(self) -> dict[str, Any]:
        return {"node_id": self.node_id, "outcome": self.outcome, "gate": self.gate, "sbm": self.sbm,
                "sbm_direction": self.sbm_direction, "sbm_target": self.sbm_target,
                "exit_evidence": list(self.exit_evidence),
                "interventions": [i.to_dict() for i in self.interventions],
                "requires_capabilities": list(self.requires_capabilities),
                "requires_relationships": list(self.requires_relationships)}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PlanNode":
        return cls.build(node_id=value["node_id"], outcome=value["outcome"], gate=value["gate"],
                         sbm=value["sbm"], sbm_direction=value["sbm_direction"], sbm_target=value["sbm_target"],
                         exit_evidence=value.get("exit_evidence", ()),
                         interventions=[InterventionSpec.from_dict(i) for i in value.get("interventions", ())],
                         requires_capabilities=value.get("requires_capabilities", ()),
                         requires_relationships=value.get("requires_relationships", ()))


@dataclass(frozen=True)
class OpportunityFactor:
    """A weak signal that, combined with others, can make a goal cheaper."""

    factor_id: str
    domain: str
    subject: str
    attribute: str
    direction: str            # gte | lte | eq | present
    threshold: float | bool | None
    weight: float
    effect: str               # favorable: cost_down | feasibility_up | timing | risk_down | upside_up
                              # threats:   cost_up | feasibility_down | risk_up | upside_down

    EFFECTS = ("cost_down", "feasibility_up", "timing", "risk_down", "upside_up")
    THREAT_EFFECTS = ("cost_up", "feasibility_down", "risk_up", "upside_down")

    @property
    def polarity(self) -> int:
        """+1 for a favorable factor, -1 for a threat; threats subtract from the intersection score."""
        return -1 if self.effect in self.THREAT_EFFECTS else 1

    @classmethod
    def build(cls, *, factor_id: str, domain: str, subject: str, attribute: str, direction: str,
              threshold: float | bool | None = None, weight: float = 1.0, effect: str) -> "OpportunityFactor":
        if direction not in DIRECTIONS + ("present",):
            raise GoalError(f"unknown factor direction {direction!r}")
        if direction != "present" and threshold is None:
            raise GoalError("factor threshold required unless direction is 'present'")
        if effect not in cls.EFFECTS + cls.THREAT_EFFECTS:
            raise GoalError(f"unknown factor effect {effect!r}")
        if threshold is not None and not isinstance(threshold, bool):
            threshold = _number("threshold", threshold)
        return cls(factor_id=require_text("factor_id", factor_id), domain=require_text("domain", domain),
                   subject=require_text("subject", subject), attribute=require_text("attribute", attribute),
                   direction=direction, threshold=threshold, weight=_number("weight", weight, minimum=0.0),
                   effect=effect)

    def to_dict(self) -> dict[str, Any]:
        return {"factor_id": self.factor_id, "domain": self.domain, "subject": self.subject,
                "attribute": self.attribute, "direction": self.direction, "threshold": self.threshold,
                "weight": self.weight, "effect": self.effect}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "OpportunityFactor":
        return cls.build(**{k: value[k] for k in ("factor_id", "domain", "subject", "attribute", "direction", "effect")},
                         threshold=value.get("threshold"), weight=value.get("weight", 1.0))


@dataclass(frozen=True)
class GoalSpec:
    """The immutable, authorized description of a goal (content-addressed)."""

    founder_intent: str
    desired_state: str
    priority: int
    authority: dict[str, Any]
    time_horizon: str
    plan: tuple[PlanNode, ...]
    relevant_entities: tuple[str, ...]
    domains: tuple[str, ...]
    wake_conditions: tuple[WakeCondition, ...]
    opportunity_factors: tuple[OpportunityFactor, ...]
    review_cadence_seconds: int
    resource_budget: dict[str, Any]
    dependencies: tuple[str, ...]
    known_opportunities: tuple[str, ...]
    known_threats: tuple[str, ...]
    missing_capabilities: tuple[str, ...]
    wake_threshold: float
    intersection_threshold: float
    intersection_window_seconds: int
    assumptions: tuple[str, ...]
    supersedes: str | None
    goal_id: str

    @classmethod
    def build(cls, *, founder_intent: str, desired_state: str, priority: int, authority: Mapping[str, Any],
              time_horizon: str, plan: Sequence[PlanNode], relevant_entities: Sequence[str] = (),
              domains: Sequence[str] = (), wake_conditions: Sequence[WakeCondition] = (),
              opportunity_factors: Sequence[OpportunityFactor] = (), review_cadence_seconds: int = 86400,
              resource_budget: Mapping[str, Any] | None = None, dependencies: Sequence[str] = (),
              known_opportunities: Sequence[str] = (), known_threats: Sequence[str] = (),
              missing_capabilities: Sequence[str] = (), wake_threshold: float = 1.0,
              intersection_threshold: float = 1.0, intersection_window_seconds: int = 30 * 86400,
              assumptions: Sequence[str] = (), supersedes: str | None = None) -> "GoalSpec":
        if priority not in PRIORITIES:
            raise GoalError("priority must be 1 (highest) to 5 (lowest)")
        auth = canonical_copy(dict(authority))
        for key in ("authorized_by", "authorization_ref", "legal_principal", "max_consequence_class"):
            auth[key] = require_text(f"authority.{key}", auth.get(key, ""))
        if auth["legal_principal"].strip().casefold() == "uniimente":
            raise GoalError("UNIIMENTE may never be the legal principal of a goal")
        if auth["max_consequence_class"] not in CONSEQUENCE_CLASSES:
            raise GoalError(f"unknown max_consequence_class {auth['max_consequence_class']!r}")
        auth.setdefault("standing_capabilities", [])
        auth["authority_note"] = "declared lineage; not founder authentication; grants no execution authority"
        nodes = tuple(plan)
        if not nodes or not all(isinstance(n, PlanNode) for n in nodes):
            raise GoalError("a goal needs at least one PlanNode")
        if len({n.node_id for n in nodes}) != len(nodes):
            raise GoalError("plan node ids must be unique")
        conds = tuple(wake_conditions)
        if not all(isinstance(c, WakeCondition) for c in conds):
            raise GoalError("wake_conditions must be WakeCondition instances")
        factors = tuple(opportunity_factors)
        if not all(isinstance(f, OpportunityFactor) for f in factors):
            raise GoalError("opportunity_factors must be OpportunityFactor instances")
        if len({f.factor_id for f in factors}) != len(factors):
            raise GoalError("factor ids must be unique")
        if not isinstance(review_cadence_seconds, int) or review_cadence_seconds <= 0:
            raise GoalError("review_cadence_seconds must be a positive integer")
        if not isinstance(intersection_window_seconds, int) or intersection_window_seconds <= 0:
            raise GoalError("intersection_window_seconds must be a positive integer")
        budget = canonical_copy(dict(resource_budget or {"max_model_calls": 4, "max_estimated_cost_usd": 0.05}))
        if not isinstance(budget.get("max_model_calls"), int) or budget["max_model_calls"] < 0:
            raise GoalError("resource_budget.max_model_calls must be a non-negative integer")
        _number("resource_budget.max_estimated_cost_usd", budget.get("max_estimated_cost_usd"), minimum=0.0)
        body = {
            "founder_intent": require_text("founder_intent", founder_intent),
            "desired_state": require_text("desired_state", desired_state),
            "priority": priority,
            "authority": auth,
            "time_horizon": require_text("time_horizon", time_horizon),
            "plan": [n.to_dict() for n in nodes],
            "relevant_entities": list(_tuple_of_text("relevant_entities", relevant_entities)),
            "domains": list(_tuple_of_text("domains", domains)),
            "wake_conditions": [c.to_dict() for c in conds],
            "opportunity_factors": [f.to_dict() for f in factors],
            "review_cadence_seconds": review_cadence_seconds,
            "resource_budget": budget,
            "dependencies": list(_tuple_of_text("dependencies", dependencies)),
            "known_opportunities": list(_tuple_of_text("known_opportunities", known_opportunities)),
            "known_threats": list(_tuple_of_text("known_threats", known_threats)),
            "missing_capabilities": list(_tuple_of_text("missing_capabilities", missing_capabilities)),
            "wake_threshold": _number("wake_threshold", wake_threshold, minimum=0.0),
            "intersection_threshold": _number("intersection_threshold", intersection_threshold, minimum=0.0),
            "intersection_window_seconds": intersection_window_seconds,
            "assumptions": list(_tuple_of_text("assumptions", assumptions)),
            "supersedes": require_text("supersedes", supersedes) if supersedes is not None else None,
        }
        goal_id = digest({"kind": "egregore-goal", **body})
        return cls(founder_intent=body["founder_intent"], desired_state=body["desired_state"], priority=priority,
                   authority=auth, time_horizon=body["time_horizon"], plan=nodes,
                   relevant_entities=tuple(body["relevant_entities"]), domains=tuple(body["domains"]),
                   wake_conditions=conds, opportunity_factors=factors,
                   review_cadence_seconds=review_cadence_seconds, resource_budget=budget,
                   dependencies=tuple(body["dependencies"]), known_opportunities=tuple(body["known_opportunities"]),
                   known_threats=tuple(body["known_threats"]), missing_capabilities=tuple(body["missing_capabilities"]),
                   wake_threshold=body["wake_threshold"], intersection_threshold=body["intersection_threshold"],
                   intersection_window_seconds=intersection_window_seconds,
                   assumptions=tuple(body["assumptions"]), supersedes=body["supersedes"], goal_id=goal_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal_id": self.goal_id, "founder_intent": self.founder_intent, "desired_state": self.desired_state,
            "priority": self.priority, "authority": canonical_copy(self.authority), "time_horizon": self.time_horizon,
            "plan": [n.to_dict() for n in self.plan], "relevant_entities": list(self.relevant_entities),
            "domains": list(self.domains), "wake_conditions": [c.to_dict() for c in self.wake_conditions],
            "opportunity_factors": [f.to_dict() for f in self.opportunity_factors],
            "review_cadence_seconds": self.review_cadence_seconds,
            "resource_budget": canonical_copy(self.resource_budget), "dependencies": list(self.dependencies),
            "known_opportunities": list(self.known_opportunities), "known_threats": list(self.known_threats),
            "missing_capabilities": list(self.missing_capabilities), "wake_threshold": self.wake_threshold,
            "intersection_threshold": self.intersection_threshold,
            "intersection_window_seconds": self.intersection_window_seconds,
            "assumptions": list(self.assumptions), "supersedes": self.supersedes,
            "execution_authority": "none",
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "GoalSpec":
        auth = dict(value["authority"])
        auth.pop("authority_note", None)
        rebuilt = cls.build(
            founder_intent=value["founder_intent"], desired_state=value["desired_state"], priority=value["priority"],
            authority=auth, time_horizon=value["time_horizon"],
            plan=[PlanNode.from_dict(n) for n in value["plan"]],
            relevant_entities=value.get("relevant_entities", ()), domains=value.get("domains", ()),
            wake_conditions=[WakeCondition.from_dict(c) for c in value.get("wake_conditions", ())],
            opportunity_factors=[OpportunityFactor.from_dict(f) for f in value.get("opportunity_factors", ())],
            review_cadence_seconds=value.get("review_cadence_seconds", 86400),
            resource_budget=value.get("resource_budget"), dependencies=value.get("dependencies", ()),
            known_opportunities=value.get("known_opportunities", ()), known_threats=value.get("known_threats", ()),
            missing_capabilities=value.get("missing_capabilities", ()), wake_threshold=value.get("wake_threshold", 1.0),
            intersection_threshold=value.get("intersection_threshold", 1.0),
            intersection_window_seconds=value.get("intersection_window_seconds", 30 * 86400),
            assumptions=value.get("assumptions", ()), supersedes=value.get("supersedes"))
        if value.get("goal_id", rebuilt.goal_id) != rebuilt.goal_id:
            raise IntegrityConflict("persisted goal_id does not match goal content")
        return rebuilt

    def node(self, node_id: str) -> PlanNode:
        for n in self.plan:
            if n.node_id == node_id:
                return n
        raise GoalError(f"unknown plan node {node_id!r}")


@dataclass
class GoalState:
    """Mutable runtime state; every change is a ledgered transition."""

    goal_id: str
    status: str = "dormant"
    current_state: dict[str, Any] = field(default_factory=dict)
    active_node_id: str | None = None
    active_gate: str | None = None
    sbm: dict[str, Any] | None = None
    blockers: list[str] = field(default_factory=list)
    missing_capabilities: list[str] = field(default_factory=list)
    missing_relationships: list[str] = field(default_factory=list)
    deficits: list[dict[str, Any]] = field(default_factory=list)
    last_reviewed_at: str | None = None
    last_woken_at: str | None = None
    wake_reason: str | None = None
    history_count: int = 0
    evidence_refs: list[str] = field(default_factory=list)
    preferences: dict[str, Any] = field(default_factory=lambda: {
        "stop_pushing": False, "priority_override": None, "never_use_tactic": [],
        "do_not_monitor": [], "ask_before": [], "refused_routes": [], "forgotten_routes": [],
        "revoked_capabilities": [], "change_notes": []})
    version: int = 0

    def to_dict(self) -> dict[str, Any]:
        return canonical_copy({
            "goal_id": self.goal_id, "status": self.status, "current_state": self.current_state,
            "active_node_id": self.active_node_id, "active_gate": self.active_gate, "sbm": self.sbm,
            "blockers": list(self.blockers), "missing_capabilities": list(self.missing_capabilities),
            "missing_relationships": list(self.missing_relationships), "deficits": list(self.deficits),
            "last_reviewed_at": self.last_reviewed_at, "last_woken_at": self.last_woken_at,
            "wake_reason": self.wake_reason, "history_count": self.history_count,
            "evidence_refs": list(self.evidence_refs), "preferences": self.preferences, "version": self.version,
            "execution_authority": "none"})

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "GoalState":
        return cls(**{k: canonical_copy(v) for k, v in value.items() if k in cls.__dataclass_fields__})


class GoalRegistry:
    """Ledger-backed goal persistence. Zero execution authority."""

    AUTHORIZED_RECORD = "egregore.goal_authorized"
    TRANSITION_RECORD = "egregore.goal_transition"
    PREFERENCE_RECORD = "egregore.goal_preference"
    CONFLICT_RECORD = "egregore.goal_conflict"

    def __init__(self, *, ledger: Any, source: str = "spiffe://uniimente.internal/egregore/goal-gravity"):
        if not all(hasattr(ledger, name) for name in ("append", "by_type", "records")):
            raise GoalError("ledger must provide append(), by_type() and records (hydration source)")
        self.ledger = ledger
        self.source = require_text("source", source)
        self._specs: dict[str, GoalSpec] = {}
        self._states: dict[str, GoalState] = {}
        self._record_hashes: dict[str, str] = {}
        self._hydrate()

    @property
    def execution_authority(self) -> str:
        return "none"

    # ------------------------------------------------------------ hydration
    def _hydrate(self) -> None:
        for record in getattr(self.ledger, "records", ()):
            rtype = getattr(record, "record_type", None)
            payload = getattr(record, "payload", {})
            if rtype == self.AUTHORIZED_RECORD:
                spec = GoalSpec.from_dict(payload["goal"])
                existing = self._specs.get(spec.goal_id)
                if existing is not None and existing.to_dict() != spec.to_dict():
                    raise IntegrityConflict("ledger contains conflicting goal content")
                self._specs[spec.goal_id] = spec
                self._record_hashes[spec.goal_id] = getattr(record, "hash", None)
                self._states.setdefault(spec.goal_id, GoalState(goal_id=spec.goal_id,
                                                                last_reviewed_at=payload.get("authorized_at"),
                                                                missing_capabilities=list(spec.missing_capabilities)))
            elif rtype in (self.TRANSITION_RECORD, self.PREFERENCE_RECORD):
                state = GoalState.from_dict(payload["state"])
                if state.goal_id not in self._specs:
                    raise IntegrityConflict("ledger transition references an unknown goal")
                self._states[state.goal_id] = state

    # ------------------------------------------------------------ queries
    def goals(self) -> list[str]:
        return sorted(self._specs)

    def get(self, goal_id: str) -> GoalSpec:
        try:
            return self._specs[goal_id]
        except KeyError as exc:
            raise GoalError(f"unknown goal {goal_id!r}") from exc

    def state(self, goal_id: str) -> GoalState:
        self.get(goal_id)
        return GoalState.from_dict(self._states[goal_id].to_dict())

    def authorization_hash(self, goal_id: str) -> str | None:
        """Ledger hash of the goal's authorization record: real evidence of declared lineage."""
        self.get(goal_id)
        return self._record_hashes.get(goal_id)

    def by_status(self, status: str) -> list[str]:
        return sorted(g for g, s in self._states.items() if s.status == status)

    def effective_priority(self, goal_id: str) -> int:
        spec, state = self.get(goal_id), self._states[goal_id]
        override = state.preferences.get("priority_override")
        return int(override) if override is not None else spec.priority

    def is_route_refused(self, goal_id: str, route_hash: str) -> bool:
        prefs = self._states[goal_id].preferences
        return route_hash in prefs.get("refused_routes", []) or route_hash in prefs.get("forgotten_routes", [])

    def tactic_forbidden(self, goal_id: str, tactic: str) -> bool:
        return bool(tactic) and tactic in self._states[goal_id].preferences.get("never_use_tactic", [])

    def domain_muted(self, goal_id: str, domain: str | None) -> bool:
        return bool(domain) and domain in self._states[goal_id].preferences.get("do_not_monitor", [])

    def ask_before(self, goal_id: str, *categories: str) -> bool:
        wanted = set(self._states[goal_id].preferences.get("ask_before", []))
        return any(c in wanted for c in categories if c)

    def capability_revoked(self, goal_id: str, capability: str) -> bool:
        return capability in self._states[goal_id].preferences.get("revoked_capabilities", [])

    def due_for_review(self, now: datetime | str) -> list[str]:
        """Dormant goals whose review cadence has elapsed. Dormancy costs nothing until now."""
        current = parse_time(now)
        due: list[str] = []
        for goal_id in self.goals():
            spec, state = self._specs[goal_id], self._states[goal_id]
            if state.status not in ("dormant", "blocked") or state.preferences.get("stop_pushing"):
                continue
            anchor = state.last_reviewed_at or state.last_woken_at
            if anchor is None or current - parse_time(anchor) >= timedelta(seconds=spec.review_cadence_seconds):
                due.append(goal_id)
        return due

    # ------------------------------------------------------------ writes
    def authorize(self, spec: GoalSpec, *, now: datetime | str) -> str:
        if not isinstance(spec, GoalSpec):
            raise GoalError("authorize requires a GoalSpec")
        spec = GoalSpec.from_dict(spec.to_dict())
        if spec.goal_id in self._specs:
            return spec.goal_id  # idempotent: identical content, identical id
        authorized_at = iso(parse_time(now))
        validate_record(spec.to_dict(), "goal-record")
        record = self.ledger.append(self.AUTHORIZED_RECORD, {
            "source": self.source, "goal": spec.to_dict(), "authorized_at": authorized_at,
            "authority_note": spec.authority["authority_note"], "disposition": "persisted_dormant"})
        self._record_hashes[spec.goal_id] = getattr(record, "hash", None)
        self._specs[spec.goal_id] = spec
        self._states[spec.goal_id] = GoalState(goal_id=spec.goal_id, last_reviewed_at=authorized_at,
                                               missing_capabilities=list(spec.missing_capabilities))
        return spec.goal_id

    def _write_state(self, record_type: str, goal_id: str, state: GoalState, *, reason: str, extra: dict | None = None) -> GoalState:
        state.version += 1
        state.history_count += 1
        validate_record(state.to_dict(), "goal-state")
        self.ledger.append(record_type, {"source": self.source, "goal_id": goal_id, "reason": require_text("reason", reason),
                                         "state": state.to_dict(), **(extra or {})})
        self._states[goal_id] = GoalState.from_dict(state.to_dict())
        return self.state(goal_id)

    def transition(self, goal_id: str, *, reason: str, now: datetime | str, status: str | None = None,
                   **fields: Any) -> GoalState:
        self.get(goal_id)
        state = self.state(goal_id)
        if state.status in ("revoked", "superseded"):
            raise GoalError(f"a {state.status} goal accepts no further transitions")
        if status is not None:
            if status not in GOAL_STATUSES:
                raise GoalError(f"unknown status {status!r}")
            state.status = status
        for key, value in fields.items():
            if key in ("goal_id", "version", "history_count", "preferences"):
                raise GoalError(f"{key} is not transition-settable")
            if key not in GoalState.__dataclass_fields__:
                raise GoalError(f"unknown state field {key!r}")
            setattr(state, key, canonical_copy(value))
        state.last_reviewed_at = iso(parse_time(now))
        return self._write_state(self.TRANSITION_RECORD, goal_id, state, reason=reason)

    def wake(self, goal_id: str, *, reason: str, now: datetime | str, signal_ids: Sequence[str] = ()) -> GoalState:
        state = self.state(goal_id)
        if state.status in ("completed", "revoked", "paused", "superseded") or state.preferences.get("stop_pushing"):
            raise GoalError(f"goal {goal_id} cannot wake from status {state.status}")
        state.status = "awake"
        state.last_woken_at = iso(parse_time(now))
        state.last_reviewed_at = state.last_woken_at
        state.wake_reason = require_text("reason", reason)
        return self._write_state(self.TRANSITION_RECORD, goal_id, state, reason=f"wake: {reason}",
                                 extra={"signal_ids": list(signal_ids)})

    def sleep(self, goal_id: str, *, reason: str, now: datetime | str, blocked: bool = False) -> GoalState:
        state = self.state(goal_id)
        if state.status in ("completed", "revoked", "superseded"):
            return state
        state.status = "blocked" if blocked else "dormant"
        state.last_reviewed_at = iso(parse_time(now))
        return self._write_state(self.TRANSITION_RECORD, goal_id, state, reason=f"sleep: {reason}")

    def supersede(self, old_goal_id: str, new_spec: GoalSpec, *, actor: str, reason: str,
                  now: datetime | str) -> str:
        """Founder 'change this goal': the old spec is immutable, so a new goal supersedes it with lineage.

        The old goal becomes ``superseded`` (never deleted); the new goal must name it in ``supersedes``.
        """
        self.get(old_goal_id)
        if not isinstance(new_spec, GoalSpec) or new_spec.supersedes != old_goal_id:
            raise GoalError("the replacement goal must declare supersedes=<old goal_id>")
        new_id = self.authorize(new_spec, now=now)
        state = self.state(old_goal_id)
        if state.status != "superseded":
            state.status = "superseded"
            state.last_reviewed_at = iso(parse_time(now))
            self._write_state(self.TRANSITION_RECORD, old_goal_id, state,
                              reason=f"superseded by {new_id[:19]} ({require_text('actor', actor)}): {reason}",
                              extra={"superseded_by": new_id})
        return new_id

    def revoke(self, goal_id: str, *, actor: str, reason: str, now: datetime | str) -> GoalState:
        state = self.state(goal_id)
        state.status = "revoked"
        state.last_reviewed_at = iso(parse_time(now))
        return self._write_state(self.TRANSITION_RECORD, goal_id, state, reason=f"revoked by {require_text('actor', actor)}: {reason}")

    def record_preference(self, goal_id: str, *, kind: str, value: Any, actor: str, reason: str,
                          now: datetime | str) -> GoalState:
        """Founder control surface: stop, change, lower, never, mute, ask-before, forget, revoke."""
        if kind not in PREFERENCE_KINDS:
            raise GoalError(f"unknown preference kind {kind!r}")
        state = self.state(goal_id)
        if state.status in ("revoked", "superseded", "completed"):
            raise GoalError(f"a {state.status} goal accepts no further preferences; authorize a new goal instead")
        prefs = state.preferences
        if kind == "stop_pushing":
            prefs["stop_pushing"] = bool(value)
            if prefs["stop_pushing"]:
                state.status = "paused"
            elif state.status == "paused":
                state.status = "dormant"
        elif kind == "lower_priority":
            if value not in PRIORITIES or value < self.effective_priority(goal_id):
                raise GoalError("lower_priority may only lower (1 highest .. 5 lowest)")
            prefs["priority_override"] = int(value)
        elif kind == "never_use_tactic":
            prefs.setdefault("never_use_tactic", []).append(require_text("tactic", value))
        elif kind == "do_not_monitor":
            prefs.setdefault("do_not_monitor", []).append(require_text("domain", value))
        elif kind == "ask_before":
            prefs.setdefault("ask_before", []).append(require_text("category", value))
        elif kind == "forget_route":
            prefs.setdefault("forgotten_routes", []).append(require_text("route_hash", value))
        elif kind == "revoke_capability":
            prefs.setdefault("revoked_capabilities", []).append(require_text("capability", value))
        elif kind == "change_goal":
            # The spec is immutable: a change pauses this goal until a replacement supersedes it.
            prefs.setdefault("change_notes", []).append(require_text("note", value))
            state.status = "paused"
        state.last_reviewed_at = iso(parse_time(now))
        return self._write_state(self.PREFERENCE_RECORD, goal_id, state, reason=f"{kind} by {require_text('actor', actor)}: {reason}",
                                 extra={"preference": {"kind": kind, "value": canonical_copy(value)}})

    def record_refusal(self, goal_id: str, *, route_hash: str, actor: str, reason: str, now: datetime | str) -> GoalState:
        state = self.state(goal_id)
        if state.status in ("revoked", "superseded", "completed"):
            raise GoalError(f"a {state.status} goal accepts no further refusals")
        state.preferences.setdefault("refused_routes", []).append(require_text("route_hash", route_hash))
        state.last_reviewed_at = iso(parse_time(now))
        return self._write_state(self.PREFERENCE_RECORD, goal_id, state, reason=f"route refused by {actor}: {reason}",
                                 extra={"preference": {"kind": "refused_route", "value": route_hash}})
