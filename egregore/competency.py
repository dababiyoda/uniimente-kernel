"""Competency Compiler seam: route each awake goal's active gate through ``capabilities/router.py``.

The router on ``main`` (PR #165) answers *which registered mechanism can know this, inside its
envelope, at the smallest competent size?* and learns only from independently verified outcomes.
It was inert: nothing called it. This module is the one caller from the founder loop:

    active gate --(PlanNode.problem_class)--> ProblemSpec --> CapabilityRouter.route
        routed      -> moves proceed; the decision id and recruited mechanisms ride on every record
        deficit     -> moves WAIT; one typed capability-deficit record; the acquisition ladder opens
        human-only  -> one founder decision item; consequential moves are prepared, never executed
        unproven    -> internal moves may run (they earn calibration); external moves are prepared
    verify_outcome (independent verifier, evidence) --> CapabilityRouter.record_outcome

A gate with no ``problem_class`` is a world state cleared by observation and is not routed;
the count of unrouted gates is reported so any future taxonomy extension has evidence behind it.
Routing confers no execution authority. The Gate and a pre-existing grant still decide.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from capabilities.router import DEFAULT_MIN_RELIABILITY, CapabilityRouter, Competency, ProblemSpec, RouterError
from .contracts import ContractError, digest
from .goals import GoalSpec
from .gps import GPSFix

OUTCOME_EVENT = "capabilities.routing_outcome"
ROUTING_EVENTS = ("capabilities.routing_decision", OUTCOME_EVENT)


@dataclass(frozen=True)
class RoutingView:
    """What one routing decision means for one goal's gate (frozen; carries no authority)."""
    decision_id: str
    problem_id: str
    problem_class: str
    selected: tuple[str, ...]
    expected_evidence: dict[str, str]
    human_escalation: tuple[str, ...]
    exploratory: bool
    requires_gate: bool
    rejected: dict[str, str]
    deficit: dict[str, Any] | None
    declared_rejected: dict[str, str] = field(default_factory=dict)
    preferred_instead: tuple[str, ...] = ()

    @property
    def routed(self) -> bool:
        return self.deficit is None

    @property
    def execution_authority(self) -> str:
        return "none"

    def to_dict(self) -> dict[str, Any]:
        return {"decision_id": self.decision_id, "problem_id": self.problem_id, "problem_class": self.problem_class,
                "selected": list(self.selected), "expected_evidence": dict(self.expected_evidence),
                "human_escalation": list(self.human_escalation), "exploratory": self.exploratory,
                "requires_gate": self.requires_gate, "rejected": dict(self.rejected), "deficit": self.deficit,
                "declared_rejected": dict(self.declared_rejected), "preferred_instead": list(self.preferred_instead),
                "routed": self.routed, "execution_authority": "none"}


class GoalCompetencyRouting:
    """Adapter that mounts the canonical router on the loop (``loop.competency``)."""

    def __init__(self, router: CapabilityRouter, *, ledger: Any, genomes: Any):
        if not isinstance(router, CapabilityRouter):
            raise ContractError("competency routing needs capabilities.router.CapabilityRouter")
        if router.ledger is not ledger:
            raise ContractError("the router must write to the one ledger the loop reads")
        if genomes is None or router.genomes is not genomes:
            raise ContractError("the router and the loop must share one genome registry")
        self.router = router
        self.ledger = ledger
        self.genomes = genomes
        self.unrouted_gates = 0
        self._applied = 0
        self.refresh(force=True)

    @property
    def execution_authority(self) -> str:
        return "none"

    # ------------------------------------------------------------ track record continuity
    def _routing_events(self) -> int:
        return sum(1 for r in self.ledger.by_type("event") if r.payload.get("type") in ROUTING_EVENTS)

    def refresh(self, *, force: bool = False) -> None:
        """Rebuild the router's decisions and calibration from the verified ledger chain when another writer
        recorded routing decisions or outcomes (or at construction). A broken chain refuses: RouterError
        propagates. This router's own writes are counted as they happen, so it does not replay itself."""
        n = self._routing_events()
        if force or n != self._applied:
            self.router.restore()
            self._applied = n

    def register(self, competency: Competency) -> Competency:
        """Pass-through: a competency must describe a genome already in the shared registry."""
        return self.router.register(competency)

    # ------------------------------------------------------------ routing
    @staticmethod
    def problem_for(spec: GoalSpec, fix: GPSFix) -> ProblemSpec | None:
        if fix.active_node_id is None:
            return None
        node = spec.node(fix.active_node_id)
        if node.problem_class is None:
            return None
        ceiling = spec.authority["max_consequence_class"]
        return ProblemSpec(
            problem_id=digest({"kind": "egregore-routing-problem", "goal_id": spec.goal_id, "node_id": node.node_id}),
            question=f"{node.gate} [{node.sbm} {node.sbm_direction} {node.sbm_target}]",
            problem_class=node.problem_class, max_consequence_class=ceiling,
            budget_usd=float((spec.resource_budget or {}).get("max_mechanism_cost_usd", 0.0)),
            # The router's own floor, deliberately not the policy evidence floor for the ceiling: under the
            # router's Beta(1,1) prior one verified success scores 0.667, so any floor above 2/3 would reject a
            # mechanism after its first success while still admitting an unproven one, and a rejected mechanism
            # can never earn the trials that would restore it. Policy floors still apply to every move.
            min_reliability=DEFAULT_MIN_RELIABILITY)

    def route_gate(self, spec: GoalSpec, fix: GPSFix) -> RoutingView | None:
        problem = self.problem_for(spec, fix)
        if problem is None:
            if fix.active_node_id is not None:
                self.unrouted_gates += 1
            return None
        self.refresh()
        decision = self.router.route(problem)
        self._applied += 1 if self.router.ledger is not None else 0
        node = spec.node(fix.active_node_id)
        declared = set(node.requires_capabilities)
        selected = tuple(c.key for c in decision.selected)
        deficit = None
        if decision.deficit is not None:
            d = decision.deficit
            deficit = {"router_deficit_id": d.deficit_id, "problem_class": d.problem_class,
                       "missing_methods": list(d.missing_methods), "rejected": dict(d.rejected),
                       "authority": d.authority}
        return RoutingView(
            decision_id=decision.decision_id, problem_id=problem.problem_id, problem_class=problem.problem_class,
            selected=selected, expected_evidence=dict(decision.expected_evidence),
            human_escalation=tuple(decision.human_escalation), exploratory=decision.exploratory,
            requires_gate=decision.requires_gate, rejected=dict(decision.rejected), deficit=deficit,
            declared_rejected={k: v for k, v in decision.rejected.items() if k in declared},
            preferred_instead=tuple(k for k in selected if declared and k not in declared))

    # ------------------------------------------------------------ outcomes
    def check_verifier(self, verifier: str, mechanisms: tuple[str, ...]) -> None:
        """The router's own independence rule, checked before anything is written."""
        for key in mechanisms:
            if verifier == key or verifier.split("@", 1)[0] == key.split("@", 1)[0]:
                raise ContractError(f"verifier {verifier!r} is the mechanism {key!r}; it may not grade itself")

    def record_outcomes(self, decision_id: str, mechanisms: tuple[str, ...], *, correct: bool,
                        evidence_ref: str, verified_by: str) -> list[dict[str, Any]]:
        results = []
        self.refresh()
        for key in mechanisms:
            try:
                cal = self.router.record_outcome(decision_id, key, correct=correct, evidence_ref=evidence_ref,
                                                 verified_by=verified_by)
                self._applied += 1
                results.append({"mechanism": key, "trials": cal.trials, "reliability": round(cal.reliability, 4)})
            except RouterError as exc:
                results.append({"mechanism": key, "refused": str(exc)[:200]})
        return results


__all__ = ["GoalCompetencyRouting", "RoutingView", "Competency"]
