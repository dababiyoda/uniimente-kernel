"""Deterministic evaluator for morphogenetic targets.

The engine estimates distance to a target, ranks bounded candidate actions, and
assesses whether a descendant proposal may be submitted for ratification. It
never executes actions and never activates descendants.
"""
from __future__ import annotations

from datetime import datetime, timezone

from .contracts import (
    ActionRecommendation,
    AssessmentState,
    AuthorityEnvelope,
    CandidateAction,
    CONSEQUENCE_CLASSES,
    DescendantProposal,
    Direction,
    FieldAssessment,
    MetricTarget,
    MorphogeneticSetPoint,
    ReplicationDecision,
    StateObservation,
)


class MorphogeneticError(ValueError):
    """Invalid control input. The engine fails closed."""


class MorphogeneticEngine:
    def __init__(self, *, confidence_floor: float = 0.70):
        if not 0.0 <= confidence_floor <= 1.0:
            raise ValueError("confidence_floor must be between 0 and 1")
        self.confidence_floor = confidence_floor

    @staticmethod
    def _error(metric: MetricTarget, value: float | bool) -> float:
        if metric.direction is Direction.EQ:
            return 0.0 if value == metric.target else 1.0
        if isinstance(value, bool) or isinstance(metric.target, bool):
            raise MorphogeneticError(f"numeric comparison required for {metric.name!r}")
        current = float(value)
        target = float(metric.target)
        scale = max(abs(target), 1.0)
        if metric.direction is Direction.GTE:
            return max(0.0, (target - current) / scale)
        if metric.direction is Direction.LTE:
            return max(0.0, (current - target) / scale)
        raise MorphogeneticError(f"unsupported direction {metric.direction!r}")

    def evaluate(
        self,
        setpoint: MorphogeneticSetPoint,
        observations: dict[str, StateObservation],
        *,
        now: datetime | None = None,
    ) -> FieldAssessment:
        problems = setpoint.validate()
        if problems:
            raise MorphogeneticError(f"invalid set-point: {problems}")
        current_time = now or datetime.now(timezone.utc)
        if current_time.tzinfo is None:
            raise MorphogeneticError("evaluation time must be timezone-aware")

        errors: dict[str, float] = {}
        blockers: list[str] = []
        for metric in setpoint.metrics:
            observation = observations.get(metric.name)
            if observation is None:
                blockers.append(f"missing observation: {metric.name}")
                continue
            observation_problems = observation.validate()
            if observation_problems:
                blockers.extend(observation_problems)
                continue
            if observation.name != metric.name:
                blockers.append(f"observation key mismatch for {metric.name}")
                continue
            if observation.contradicted:
                blockers.append(f"contradicted observation: {metric.name}")
                continue
            if observation.confidence < self.confidence_floor:
                blockers.append(
                    f"low-confidence observation: {metric.name} "
                    f"({observation.confidence:.2f} < {self.confidence_floor:.2f})"
                )
                continue
            if metric.max_age_seconds is not None:
                age = (current_time - observation.observed_at).total_seconds()
                if age < 0:
                    blockers.append(f"future-dated observation: {metric.name}")
                    continue
                if age > metric.max_age_seconds:
                    blockers.append(f"stale observation: {metric.name}")
                    continue
            errors[metric.name] = self._error(metric, observation.value)

        if current_time > setpoint.deadline:
            blockers.append("set-point deadline expired")

        target_reached = not blockers and all(error == 0.0 for error in errors.values())
        if blockers:
            state = AssessmentState.INSUFFICIENT_EVIDENCE
        elif target_reached:
            state = AssessmentState.TARGET_REACHED_NOT_AUTHORIZED
        else:
            state = AssessmentState.TARGET_NOT_REACHED
        return FieldAssessment(
            state=state,
            errors=errors,
            blockers=tuple(blockers),
            target_reached=target_reached,
            can_request_gate=target_reached and setpoint.requires_human_activation,
        )

    def rank_actions(
        self,
        setpoint: MorphogeneticSetPoint,
        observations: dict[str, StateObservation],
        actions: tuple[CandidateAction, ...],
        envelope: AuthorityEnvelope,
    ) -> tuple[ActionRecommendation, ...]:
        if setpoint.validate():
            raise MorphogeneticError("invalid set-point")
        envelope_problems = envelope.validate()
        if envelope_problems:
            raise MorphogeneticError(f"invalid authority envelope: {envelope_problems}")

        current_errors: dict[str, float] = {}
        targets = {metric.name: metric for metric in setpoint.metrics}
        for name, metric in targets.items():
            observation = observations.get(name)
            if observation is not None and not observation.validate() and not observation.contradicted:
                current_errors[name] = self._error(metric, observation.value)

        recommendations: list[ActionRecommendation] = []
        envelope_index = CONSEQUENCE_CLASSES.index(envelope.max_consequence_class)
        prohibited = set(envelope.prohibited_actions) | set(setpoint.prohibited_actions)
        permitted = set(envelope.permitted_actions)

        for action in actions:
            problems = action.validate()
            if problems:
                continue
            if action.action_id in prohibited:
                continue
            if permitted and action.action_id not in permitted:
                continue
            if CONSEQUENCE_CLASSES.index(action.consequence_class) > envelope_index:
                continue
            if action.estimated_cost_usd > envelope.budget_remaining_usd:
                continue
            if action.consequence_class in {"external_contact", "financial", "irreversible"} and not action.requires_human:
                continue

            improvement = 0.0
            for name, projected in action.projected_values.items():
                metric = targets.get(name)
                if metric is None or name not in current_errors:
                    continue
                projected_error = self._error(metric, projected)
                improvement += max(0.0, current_errors[name] - projected_error) * metric.weight
            if improvement <= 0:
                continue
            cost_penalty = action.estimated_cost_usd / max(setpoint.budget_ceiling_usd, 1.0)
            score = improvement - cost_penalty
            recommendations.append(
                ActionRecommendation(
                    action_id=action.action_id,
                    score=score,
                    reason="expected target-error reduction inside current authority envelope",
                    requires_gate=action.consequence_class in {"external_contact", "financial", "irreversible"},
                )
            )

        return tuple(sorted(recommendations, key=lambda item: (-item.score, item.action_id)))

    def assess_descendant(
        self,
        parent_assessment: FieldAssessment,
        proposal: DescendantProposal,
    ) -> ReplicationDecision:
        problems = proposal.validate()
        if problems:
            return ReplicationDecision(status="BLOCKED", reasons=tuple(problems))
        if not parent_assessment.target_reached:
            return ReplicationDecision(
                status="BLOCKED",
                reasons=("parent Venture Cell has not reached validated target state",),
            )
        return ReplicationDecision(
            status="MAY_REQUEST_RATIFICATION",
            reasons=(
                "parent target is closed",
                "proposal is bounded",
                "human ratification and Consequence Gate receipt remain mandatory",
            ),
            proposal=proposal,
        )
