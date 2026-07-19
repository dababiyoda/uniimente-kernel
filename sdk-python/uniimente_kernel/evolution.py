"""First Evolution Cycle: the machine-recorded improvement machinery.

Eight primitives from the Final Plan, one ledger-integrated flow:

    bottleneck -> StrategyTree of materially different StrategyBranches
    -> selection (the preferred idea never wins by default; rejected
    branches are preserved with loss reasons and revival evidence)
    -> SpiderWebAudit across exactly eight sides
    -> ExperimentSpec for the decisive unknown (smallest reversible test)
    -> execution outcome compared against the previous baseline
    -> ClosureController verdict (FALSELY CLOSED triggers investigation)
    -> RetainRegressKillDecision gated by the verifier hierarchy
    -> EvolutionCapsule: the immutable, ledgered record of the cycle.

Sovereignty rule, mechanical: a VerifierRecord at level 6 (same-model
critique) or 7 (intrinsic confidence) may generate hypotheses. It may
never authorize a RETAIN decision. The system’s opinion of itself is
not evidence.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Any, Dict, List, Optional, Tuple

from uniimente_kernel.ledger import DecisionLedger

# --- Plan-mandated vocabularies ---------------------------------------- #

BRANCH_ARCHETYPES = (
    "fastest_path",
    "lowest_capital",
    "maximum_ownership",
    "maximum_reversibility",
    "maximum_regeneration",
    "strongest_partnership",
    "acquisition",
    "incumbent_compatible",
    "radical_simplification",
    "complete_removal",
    "do_nothing",
)

SPIDER_SIDES = (
    "reality_failure_geometry",
    "power_participant_geometry",
    "eligibility_permission",
    "default_routing_access",
    "proof_truth_reputation",
    "settlement_capital_physics",
    "distribution_entanglement_counterposition",
    "reliability_governance_regeneration_continuity",
)

SUPER_NODES = frozenset({
    "eligibility",
    "default_routing",
    "proof_and_truth",
    "cashflow_and_settlement",
})

SPIDER_REQUIREMENTS = (
    "bounded_transaction",
    "real_beneficiary",
    "buyer_or_mandate_actor",
    "lawful_permission_path",
    "accepted_artifact",
    "external_consequence",
    "participant_benefit",
    "ninety_day_falsification_test",
    "fundable_reliability",
    "recovery",
    "kill_criteria",
)

CLOSURE_STATES = frozenset({"closed", "partially_closed", "falsely_closed", "open"})

VERIFIER_LEVELS = {
    1: "formal_proof_or_deterministic_invariant",
    2: "independently_observable_external_outcome",
    3: "cryptographically_verified_external_receipt",
    4: "qualified_human_or_expert_review",
    5: "independent_model_or_agent_review",
    6: "same_model_critique",
    7: "intrinsic_confidence",
}
#: Levels that may authorize institutional promotion. Six and seven may
#: only generate hypotheses.
PROMOTION_AUTHORIZING_LEVELS = frozenset({1, 2, 3, 4, 5})

DECISIONS = frozenset({"retain", "regress", "kill"})

BRANCH_STATUSES = frozenset({"proposed", "selected", "rejected", "revived"})


class EvolutionError(ValueError):
    """Raised when a cycle artifact violates its contract."""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _require(fields: Dict[str, Any], owner: str) -> None:
    missing = [k for k, v in fields.items() if v is None or v == "" or v == []]
    if missing:
        raise EvolutionError(f"{owner} missing required fields: {missing}")


# --- StrategyBranch / StrategyTree ------------------------------------- #

@dataclass
class StrategyBranch:
    """One materially different route for a bottleneck."""

    archetype: str
    governing_assumption: str
    mechanism: str
    required_capabilities: List[str]
    cost_usd: float
    founder_attention_minutes: int
    time_to_proof_days: int
    authority_requirements: List[str]
    irreversible_downside: str
    expected_result: str
    strongest_counterargument: str
    cheapest_falsification_test: str
    kill_condition: str
    bottleneck: str = ""
    branch_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: str = "proposed"
    loss_reason: Optional[str] = None
    revival_evidence: Optional[str] = None

    def validate(self) -> "StrategyBranch":
        if self.archetype not in BRANCH_ARCHETYPES:
            raise EvolutionError(
                f"archetype must be one of {list(BRANCH_ARCHETYPES)}"
            )
        if self.status not in BRANCH_STATUSES:
            raise EvolutionError(f"status must be one of {sorted(BRANCH_STATUSES)}")
        _require({
            "governing_assumption": self.governing_assumption,
            "mechanism": self.mechanism,
            "required_capabilities": self.required_capabilities,
            "authority_requirements": self.authority_requirements,
            "irreversible_downside": self.irreversible_downside,
            "expected_result": self.expected_result,
            "strongest_counterargument": self.strongest_counterargument,
            "cheapest_falsification_test": self.cheapest_falsification_test,
            "kill_condition": self.kill_condition,
        }, f"StrategyBranch({self.archetype})")
        if self.cost_usd < 0 or self.founder_attention_minutes < 0 or self.time_to_proof_days < 0:
            raise EvolutionError("costs cannot be negative")
        return self

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in vars(self).items()}


class StrategyTree:
    """The branches for one bottleneck, with honest selection rules."""

    def __init__(self, ledger: DecisionLedger, *, bottleneck: str) -> None:
        if not bottleneck:
            raise EvolutionError("bottleneck is required")
        self.ledger = ledger
        self.bottleneck = bottleneck
        self.branches: Dict[str, StrategyBranch] = {}

    def add(self, branch: StrategyBranch) -> StrategyBranch:
        branch.bottleneck = self.bottleneck
        branch.validate()
        self.branches[branch.branch_id] = branch
        self.ledger.record("strategy_branch_proposed", {
            "bottleneck": self.bottleneck,
            "branch_id": branch.branch_id,
            "archetype": branch.archetype,
        })
        return branch

    def missing_archetypes(self) -> List[str]:
        present = {b.archetype for b in self.branches.values()}
        return [a for a in BRANCH_ARCHETYPES if a not in present]

    def select(
        self,
        branch_id: str,
        *,
        decider: str,
        rationale: str,
        loss_reasons: Dict[str, str],
        revival_evidence: Optional[Dict[str, str]] = None,
    ) -> StrategyBranch:
        """Select one branch; preserve every loser with why it lost.

        The preferred idea never wins by default: selection is refused
        until all eleven archetypes have been honestly generated, and
        every non-selected branch must carry a loss reason.
        """
        missing = self.missing_archetypes()
        if missing:
            raise EvolutionError(
                f"cannot select: archetypes not yet generated: {missing}"
            )
        if branch_id not in self.branches:
            raise EvolutionError(f"unknown branch: {branch_id}")
        if not rationale:
            raise EvolutionError("selection rationale is required")
        for loser_id, branch in self.branches.items():
            if loser_id == branch_id:
                continue
            reason = loss_reasons.get(loser_id)
            if not reason:
                raise EvolutionError(
                    f"loss reason required for rejected branch {branch.archetype}"
                )
            branch.status = "rejected"
            branch.loss_reason = reason
            branch.revival_evidence = (revival_evidence or {}).get(loser_id)
            self.ledger.record("strategy_branch_rejected", {
                "bottleneck": self.bottleneck,
                "branch_id": loser_id,
                "archetype": branch.archetype,
                "loss_reason": reason,
                "revival_evidence": branch.revival_evidence,
            })
        winner = self.branches[branch_id]
        winner.status = "selected"
        self.ledger.record("strategy_branch_selected", {
            "bottleneck": self.bottleneck,
            "branch_id": branch_id,
            "archetype": winner.archetype,
            "decider": decider,
            "rationale": rationale,
        })
        return winner

    def rejected(self) -> List[StrategyBranch]:
        return [b for b in self.branches.values() if b.status == "rejected"]


# --- SpiderWebAudit ----------------------------------------------------- #

@dataclass
class SpiderWebAudit:
    """A surviving strategy tested as a complete institution, eight sides."""

    branch_id: str
    sides: Dict[str, str]
    mechanism_map: Dict[str, Optional[str]]
    requirements: Dict[str, bool]
    audit_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def decorative_mechanisms(self) -> List[str]:
        """Mechanisms mapping to no governing super-node: remove them."""
        return [m for m, node in self.mechanism_map.items() if node not in SUPER_NODES]

    def evaluate(self) -> Tuple[bool, List[str]]:
        failures: List[str] = []
        missing_sides = [s for s in SPIDER_SIDES if not self.sides.get(s)]
        if missing_sides:
            failures.append(f"sides without findings: {missing_sides}")
        decorative = self.decorative_mechanisms()
        if decorative:
            failures.append(f"decorative mechanisms (map to no super-node): {decorative}")
        unmet = [r for r in SPIDER_REQUIREMENTS if not self.requirements.get(r)]
        if unmet:
            failures.append(f"requirements unmet: {unmet}")
        return (not failures, failures)


# --- ExperimentSpec ----------------------------------------------------- #

@dataclass
class ExperimentSpec:
    """The smallest reversible experiment resolving the decisive unknown."""

    decisive_unknown: str
    hypothesis: str
    method: str
    metrics: Dict[str, str]  # metric name -> "higher" | "lower"
    baseline: Dict[str, float]
    reversibility: str  # must be "reversible"
    budget_usd: float
    kill_condition: str
    experiment_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def validate(self) -> "ExperimentSpec":
        _require({
            "decisive_unknown": self.decisive_unknown,
            "hypothesis": self.hypothesis,
            "method": self.method,
            "metrics": self.metrics,
            "baseline": self.baseline,
            "kill_condition": self.kill_condition,
        }, "ExperimentSpec")
        if self.reversibility != "reversible":
            raise EvolutionError(
                "experiment must be reversible; the plan admits no other kind"
            )
        for name, direction in self.metrics.items():
            if direction not in ("higher", "lower"):
                raise EvolutionError(f"metric {name}: direction must be higher|lower")
            if name not in self.baseline:
                raise EvolutionError(f"metric {name}: no baseline value")
        if self.budget_usd < 0:
            raise EvolutionError("budget cannot be negative")
        return self

    def beats_baseline(self, outcome: Dict[str, float]) -> bool:
        """Strict improvement on every metric, in its own direction."""
        for name, direction in self.metrics.items():
            if name not in outcome:
                return False
            base, observed = self.baseline[name], outcome[name]
            if direction == "higher" and not observed > base:
                return False
            if direction == "lower" and not observed < base:
                return False
        return True


# --- VerifierRecord ----------------------------------------------------- #

@dataclass
class VerifierRecord:
    """Which verifier judged the outcome, at what hierarchy level."""

    level: int
    verifier_name: str
    evidence_ref: str  # sha256:... of the evidence artifact
    recorded_at: str = field(default_factory=_now)

    def validate(self) -> "VerifierRecord":
        if self.level not in VERIFIER_LEVELS:
            raise EvolutionError(f"level must be 1-7 ({sorted(VERIFIER_LEVELS)})")
        _require({
            "verifier_name": self.verifier_name,
            "evidence_ref": self.evidence_ref,
        }, "VerifierRecord")
        return self

    @property
    def may_authorize_promotion(self) -> bool:
        return self.level in PROMOTION_AUTHORIZING_LEVELS


# --- ClosureController -------------------------------------------------- #

class ClosureController:
    """Whole-body closure verdicts. False closure triggers investigation."""

    def __init__(self, ledger: DecisionLedger) -> None:
        self.ledger = ledger

    def evaluate(
        self,
        change_id: str,
        *,
        internal_metric_met: bool,
        external_consequence_met: bool,
        evidence_refs: Optional[List[str]] = None,
    ) -> str:
        if internal_metric_met and external_consequence_met:
            state = "closed"
        elif internal_metric_met:
            state = "falsely_closed"
        elif external_consequence_met:
            state = "partially_closed"
        else:
            state = "open"
        self.ledger.record("closure_evaluated", {
            "change_id": change_id,
            "state": state,
            "internal_metric_met": internal_metric_met,
            "external_consequence_met": external_consequence_met,
            "evidence_refs": evidence_refs or [],
        })
        if state == "falsely_closed":
            # Internal metric satisfied without the intended external
            # consequence: investigate and regress, never celebrate.
            self.ledger.record("closure_investigation_opened", {
                "change_id": change_id,
                "reason": "internal metric met without external consequence",
            })
        return state


# --- RetainRegressKillDecision ------------------------------------------ #

@dataclass
class RetainRegressKillDecision:
    decision: str
    rationale: str
    evidence_refs: List[str]
    verifier: VerifierRecord
    decided_at: str = field(default_factory=_now)

    def validate(self) -> "RetainRegressKillDecision":
        if self.decision not in DECISIONS:
            raise EvolutionError(f"decision must be one of {sorted(DECISIONS)}")
        _require({
            "rationale": self.rationale,
            "evidence_refs": self.evidence_refs,
        }, "RetainRegressKillDecision")
        self.verifier.validate()
        if self.decision == "retain" and not self.verifier.may_authorize_promotion:
            raise EvolutionError(
                f"verifier level {self.verifier.level} "
                f"({VERIFIER_LEVELS[self.verifier.level]}) may generate "
                "hypotheses but may not authorize a retain decision"
            )
        return self

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision,
            "rationale": self.rationale,
            "evidence_refs": self.evidence_refs,
            "verifier": {
                "level": self.verifier.level,
                "level_name": VERIFIER_LEVELS[self.verifier.level],
                "verifier_name": self.verifier.verifier_name,
                "evidence_ref": self.verifier.evidence_ref,
                "recorded_at": self.verifier.recorded_at,
            },
            "decided_at": self.decided_at,
        }


# --- EvolutionCapsule --------------------------------------------------- #

class EvolutionCapsule:
    """One complete, machine-recorded improvement cycle."""

    def __init__(self, ledger: DecisionLedger) -> None:
        self.ledger = ledger
        self.closure = ClosureController(ledger)

    def complete_cycle(
        self,
        *,
        bottleneck: str,
        tree: StrategyTree,
        selected_branch_id: str,
        audit: SpiderWebAudit,
        experiment: ExperimentSpec,
        outcome: Dict[str, float],
        outcome_evidence_refs: List[str],
        verifier: VerifierRecord,
        kill_condition_fired: bool = False,
        internal_metric_met: bool = True,
        external_consequence_met: bool = True,
        rationale: str = "",
    ) -> Dict[str, Any]:
        """Close one cycle and ledger the capsule.

        Decision precedence: KILL if the kill condition fired; REGRESS
        if the audit fails, closure is false, the outcome does not beat
        baseline, or the verifier may not authorize promotion; RETAIN
        only when every gate clears.
        """
        experiment.validate()
        audit_ok, audit_failures = audit.evaluate()
        self.ledger.record("spider_web_audit", {
            "audit_id": audit.audit_id,
            "branch_id": audit.branch_id,
            "verdict": "pass" if audit_ok else "fail",
            "failures": audit_failures,
        })

        closure_state = self.closure.evaluate(
            experiment.experiment_id,
            internal_metric_met=internal_metric_met,
            external_consequence_met=external_consequence_met,
            evidence_refs=outcome_evidence_refs,
        )
        beats = experiment.beats_baseline(outcome)

        if kill_condition_fired:
            decision, reason = "kill", "kill condition fired"
        elif not audit_ok:
            decision, reason = "regress", f"spider-web audit failed: {audit_failures}"
        elif closure_state == "falsely_closed":
            decision, reason = "regress", "false closure: internal metric without external consequence"
        elif not beats:
            decision, reason = "regress", "outcome did not beat baseline"
        elif not verifier.may_authorize_promotion:
            decision, reason = "regress", (
                f"verifier level {verifier.level} may not authorize promotion"
            )
        elif closure_state != "closed":
            decision, reason = "regress", f"closure state {closure_state} is not closed"
        else:
            decision, reason = "retain", rationale or "beats baseline with authorizing verification"

        verdict = RetainRegressKillDecision(
            decision=decision,
            rationale=reason,
            evidence_refs=outcome_evidence_refs,
            verifier=verifier,
        )
        # A regress/kill decision is always constructible; a retain that
        # slipped past the gates is rejected here by validate().
        verdict.validate()

        capsule = {
            "capsule_id": str(uuid.uuid4()),
            "recorded_at": _now(),
            "bottleneck": bottleneck,
            "tree": {
                "bottleneck": tree.bottleneck,
                "branches": [b.to_dict() for b in tree.branches.values()],
                "selected_branch_id": selected_branch_id,
            },
            "spider_web_audit": {
                "audit_id": audit.audit_id,
                "verdict": "pass" if audit_ok else "fail",
                "failures": audit_failures,
                "decorative_mechanisms": audit.decorative_mechanisms(),
            },
            "experiment": {
                "experiment_id": experiment.experiment_id,
                "decisive_unknown": experiment.decisive_unknown,
                "hypothesis": experiment.hypothesis,
                "metrics": experiment.metrics,
                "baseline": experiment.baseline,
            },
            "outcome": outcome,
            "beats_baseline": beats,
            "closure_state": closure_state,
            "decision": verdict.to_dict(),
        }
        self.ledger.record("evolution_cycle_completed", {
            "capsule_id": capsule["capsule_id"],
            "bottleneck": bottleneck,
            "decision": decision,
            "beats_baseline": beats,
            "closure_state": closure_state,
            "verifier_level": verifier.level,
            "evidence_refs": outcome_evidence_refs,
        })
        return capsule


__all__ = [
    "BRANCH_ARCHETYPES",
    "BRANCH_STATUSES",
    "CLOSURE_STATES",
    "ClosureController",
    "DECISIONS",
    "EvolutionCapsule",
    "EvolutionError",
    "ExperimentSpec",
    "PROMOTION_AUTHORIZING_LEVELS",
    "RetainRegressKillDecision",
    "SPIDER_REQUIREMENTS",
    "SPIDER_SIDES",
    "SUPER_NODES",
    "SpiderWebAudit",
    "StrategyBranch",
    "StrategyTree",
    "VERIFIER_LEVELS",
    "VerifierRecord",
]
