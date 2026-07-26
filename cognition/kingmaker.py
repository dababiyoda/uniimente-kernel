"""Cognitive Kingmaker protocol.

This module selects which model should attack which problem. It deliberately
contains no provider client, credentials, model invocation, or execution path.
Its only output is a cost-bounded, proposal-only routing decision.

The Kernel invariant remains unchanged:

    models reason -> agents propose -> humans and policies authorize
    -> the Kernel determines what may become real

A model is a replaceable cognitive organelle. It never becomes the identity,
legal principal, memory authority, or consequence boundary of UNIIMENTE.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from typing import Iterable


class RoutingError(ValueError):
    """The routing request is invalid or cannot be satisfied safely."""


class CognitiveRole(str, Enum):
    FOUNDER_INTENT_GOVERNOR = "founder_intent_governor"
    NOVELTY_ARCHITECT = "novelty_architect"
    INSTITUTIONAL_COMPILER = "institutional_compiler"
    IMPLEMENTATION_SPECIALIST = "implementation_specialist"
    ADVERSARIAL_REVIEWER = "adversarial_reviewer"
    EVIDENCE_AUDITOR = "evidence_auditor"


class ConsequenceClass(str, Enum):
    READ_ONLY = "read_only"
    INTERNAL_WRITE = "internal_write"
    EXTERNAL_CONTACT = "external_contact"
    FINANCIAL = "financial"
    IRREVERSIBLE = "irreversible"


_CONSEQUENCE_ORDER = {
    ConsequenceClass.READ_ONLY: 0,
    ConsequenceClass.INTERNAL_WRITE: 1,
    ConsequenceClass.EXTERNAL_CONTACT: 2,
    ConsequenceClass.FINANCIAL: 3,
    ConsequenceClass.IRREVERSIBLE: 4,
}


@dataclass(frozen=True)
class FounderIntentPacket:
    """Minimal founder context needed for one bounded cognitive mission."""

    intent_ref: str
    mission: str
    protected_invariants: tuple[str, ...]
    current_architecture_refs: tuple[str, ...]
    unresolved_contradiction: str

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not self.intent_ref.strip():
            problems.append("founder intent reference is required")
        if not self.mission.strip():
            problems.append("founder mission is required")
        if not self.protected_invariants:
            problems.append("at least one protected invariant is required")
        if any(not item.strip() for item in self.protected_invariants):
            problems.append("protected invariants may not be blank")
        if any(not item.strip() for item in self.current_architecture_refs):
            problems.append("architecture references may not be blank")
        if not self.unresolved_contradiction.strip():
            problems.append("the unresolved contradiction is required")
        return problems


@dataclass(frozen=True)
class ModelProfile:
    """Evidence-backed provider profile supplied by the runtime registry.

    Scores are local calibration measurements in [0, 1], not vendor claims.
    The router never assumes that cost, brand, or benchmark rank implies
    universal superiority.
    """

    model_id: str
    provider: str
    capabilities: frozenset[str]
    novelty_score: float
    intent_continuity_score: float
    synthesis_score: float
    implementation_score: float
    adversarial_score: float
    evidence_score: float
    input_cost_per_million: float
    output_cost_per_million: float
    calibration_evidence_ref: str
    enabled: bool = True

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not self.model_id.strip():
            problems.append("model_id is required")
        if not self.provider.strip():
            problems.append("provider is required")
        if not self.calibration_evidence_ref.strip():
            problems.append(f"{self.model_id}: calibration evidence reference is required")
        for name in (
            "novelty_score",
            "intent_continuity_score",
            "synthesis_score",
            "implementation_score",
            "adversarial_score",
            "evidence_score",
        ):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                problems.append(f"{self.model_id}: {name} must be in [0, 1]")
        if self.input_cost_per_million < 0 or self.output_cost_per_million < 0:
            problems.append(f"{self.model_id}: model prices may not be negative")
        return problems

    def estimated_cost(self, input_tokens: int, output_tokens: int) -> float:
        return (
            input_tokens * self.input_cost_per_million
            + output_tokens * self.output_cost_per_million
        ) / 1_000_000.0


@dataclass(frozen=True)
class WorkRequest:
    request_id: str
    objective: str
    intent: FounderIntentPacket
    required_capabilities: frozenset[str]
    ambiguity: float
    novelty_required: bool
    implementation_required: bool
    evidence_required: bool
    dissent_required: bool
    consequence_class: ConsequenceClass
    irreversible: bool
    budget_ceiling_usd: float
    expected_input_tokens_per_call: int
    expected_output_tokens_per_call: int

    def validate(self) -> list[str]:
        problems = self.intent.validate()
        if not self.request_id.strip():
            problems.append("request_id is required")
        if not self.objective.strip():
            problems.append("objective is required")
        if not 0.0 <= self.ambiguity <= 1.0:
            problems.append("ambiguity must be in [0, 1]")
        if self.budget_ceiling_usd < 0:
            problems.append("budget ceiling may not be negative")
        if self.expected_input_tokens_per_call < 0:
            problems.append("expected input tokens may not be negative")
        if self.expected_output_tokens_per_call < 0:
            problems.append("expected output tokens may not be negative")
        if self.irreversible and self.consequence_class != ConsequenceClass.IRREVERSIBLE:
            problems.append("irreversible work must use consequence_class=irreversible")
        return problems


@dataclass(frozen=True)
class RouteStep:
    role: CognitiveRole
    model_id: str
    provider: str
    purpose: str
    estimated_cost_usd: float
    max_calls: int = 1
    output_status: str = "PROPOSED_NOT_EXECUTED"


@dataclass(frozen=True)
class RoutingDecision:
    decision_id: str
    request_id: str
    steps: tuple[RouteStep, ...]
    total_estimated_cost_usd: float
    reasons: tuple[str, ...]
    refused: bool
    refusal_reasons: tuple[str, ...]
    requires_human_ratification: bool
    model_output_is_evidence: bool = False
    external_effect_authorized: bool = False


@dataclass(frozen=True)
class InventionPacket:
    packet_id: str
    request_id: str
    assigned_model_id: str
    founder_intent_ref: str
    objective: str
    current_architecture_refs: tuple[str, ...]
    protected_invariants: tuple[str, ...]
    unresolved_contradiction: str
    required_routes: tuple[str, ...]
    adversarial_obligations: tuple[str, ...]
    integration_outputs: tuple[str, ...]
    authority_status: str = "PROPOSED_NOT_EXECUTED"


class CognitiveKingmaker:
    """Routes bounded cognitive work to measured model strengths.

    The router is intentionally deterministic for the same request and model
    registry. It does not invoke a model and cannot create authority.
    """

    def __init__(self, profiles: Iterable[ModelProfile]):
        self._profiles = tuple(profiles)
        if not self._profiles:
            raise RoutingError("at least one model profile is required")
        problems = [p for profile in self._profiles for p in profile.validate()]
        if problems:
            raise RoutingError(f"invalid model registry: {problems}")
        ids = [profile.model_id for profile in self._profiles]
        if len(ids) != len(set(ids)):
            raise RoutingError("model_id values must be unique")

    def _eligible(self, request: WorkRequest) -> tuple[ModelProfile, ...]:
        return tuple(
            profile
            for profile in self._profiles
            if profile.enabled
            and request.required_capabilities.issubset(profile.capabilities)
        )

    @staticmethod
    def _select(
        profiles: tuple[ModelProfile, ...],
        score_field: str,
        *,
        exclude_model_ids: frozenset[str] = frozenset(),
    ) -> ModelProfile | None:
        candidates = [p for p in profiles if p.model_id not in exclude_model_ids]
        if not candidates:
            return None
        return max(
            candidates,
            key=lambda p: (
                getattr(p, score_field),
                -p.input_cost_per_million,
                -p.output_cost_per_million,
                p.model_id,
            ),
        )

    @staticmethod
    def _step(
        request: WorkRequest,
        role: CognitiveRole,
        profile: ModelProfile,
        purpose: str,
    ) -> RouteStep:
        return RouteStep(
            role=role,
            model_id=profile.model_id,
            provider=profile.provider,
            purpose=purpose,
            estimated_cost_usd=round(
                profile.estimated_cost(
                    request.expected_input_tokens_per_call,
                    request.expected_output_tokens_per_call,
                ),
                6,
            ),
        )

    @staticmethod
    def _decision_id(request: WorkRequest, steps: list[RouteStep], refused: bool) -> str:
        payload = {
            "request_id": request.request_id,
            "steps": [
                {"role": step.role.value, "model_id": step.model_id}
                for step in steps
            ],
            "refused": refused,
        }
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return f"sha256:{digest}"

    def route(self, request: WorkRequest) -> RoutingDecision:
        problems = request.validate()
        if problems:
            raise RoutingError(f"invalid work request: {problems}")

        eligible = self._eligible(request)
        refusal_reasons: list[str] = []
        reasons: list[str] = []
        steps: list[RouteStep] = []

        if not eligible:
            refusal_reasons.append(
                "no enabled model satisfies the request's required capabilities"
            )

        intent_model = self._select(eligible, "intent_continuity_score")
        if intent_model is None:
            refusal_reasons.append("no founder-intent governor is available")
        else:
            steps.append(
                self._step(
                    request,
                    CognitiveRole.FOUNDER_INTENT_GOVERNOR,
                    intent_model,
                    "compress founder intent, preserve protected invariants, and frame the exact problem",
                )
            )
            reasons.append(
                f"{intent_model.model_id} has the strongest calibrated intent-continuity score"
            )

        lead_model: ModelProfile | None = None
        needs_novelty = request.novelty_required or request.ambiguity >= 0.65
        if needs_novelty:
            lead_model = self._select(eligible, "novelty_score")
            if lead_model is None:
                refusal_reasons.append("novelty was required but no novelty architect is available")
            else:
                steps.append(
                    self._step(
                        request,
                        CognitiveRole.NOVELTY_ARCHITECT,
                        lead_model,
                        "search beyond the current architecture and generate materially different mechanisms",
                    )
                )
                reasons.append(
                    f"{lead_model.model_id} has the strongest calibrated novelty score"
                )
        elif request.implementation_required:
            lead_model = self._select(eligible, "implementation_score")
            if lead_model is None:
                refusal_reasons.append("implementation was required but no implementation specialist is available")
            else:
                steps.append(
                    self._step(
                        request,
                        CognitiveRole.IMPLEMENTATION_SPECIALIST,
                        lead_model,
                        "produce the bounded implementation proposal and acceptance tests",
                    )
                )
                reasons.append(
                    f"{lead_model.model_id} has the strongest calibrated implementation score"
                )
        else:
            lead_model = self._select(eligible, "synthesis_score")

        compiler = self._select(eligible, "synthesis_score")
        if compiler is None:
            refusal_reasons.append("no institutional compiler is available")
        else:
            steps.append(
                self._step(
                    request,
                    CognitiveRole.INSTITUTIONAL_COMPILER,
                    compiler,
                    "translate surviving cognition into contracts, interfaces, tests, failure conditions, and repository placement",
                )
            )
            reasons.append(
                f"{compiler.model_id} has the strongest calibrated synthesis score"
            )

        high_consequence = (
            _CONSEQUENCE_ORDER[request.consequence_class]
            >= _CONSEQUENCE_ORDER[ConsequenceClass.EXTERNAL_CONTACT]
        )

        if request.dissent_required or high_consequence:
            excluded = frozenset({lead_model.model_id}) if lead_model is not None else frozenset()
            adversary = self._select(
                eligible,
                "adversarial_score",
                exclude_model_ids=excluded,
            )
            if adversary is None:
                refusal_reasons.append(
                    "independent dissent was required but no second model is available"
                )
            else:
                steps.append(
                    self._step(
                        request,
                        CognitiveRole.ADVERSARIAL_REVIEWER,
                        adversary,
                        "attack the lead proposal, expose hidden assumptions, and preserve the strongest dissent",
                    )
                )
                reasons.append(
                    f"{adversary.model_id} provides provider-diverse adversarial review"
                )

        if request.evidence_required or high_consequence:
            excluded = frozenset({lead_model.model_id}) if high_consequence and lead_model else frozenset()
            auditor = self._select(
                eligible,
                "evidence_score",
                exclude_model_ids=excluded,
            )
            if auditor is None:
                refusal_reasons.append("required evidence audit cannot be independently staffed")
            else:
                steps.append(
                    self._step(
                        request,
                        CognitiveRole.EVIDENCE_AUDITOR,
                        auditor,
                        "separate claims from evidence and define the external verification obligation",
                    )
                )
                reasons.append(
                    f"{auditor.model_id} has the strongest eligible evidence-audit score"
                )

        total = round(sum(step.estimated_cost_usd for step in steps), 6)
        if total > request.budget_ceiling_usd:
            refusal_reasons.append(
                f"estimated cognitive cost ${total:.6f} exceeds budget ceiling "
                f"${request.budget_ceiling_usd:.6f}"
            )

        refused = bool(refusal_reasons)
        requires_human = high_consequence or request.irreversible
        return RoutingDecision(
            decision_id=self._decision_id(request, steps, refused),
            request_id=request.request_id,
            steps=tuple(steps),
            total_estimated_cost_usd=total,
            reasons=tuple(reasons),
            refused=refused,
            refusal_reasons=tuple(refusal_reasons),
            requires_human_ratification=requires_human,
        )


_REQUIRED_NOVELTY_ROUTES = (
    "five materially different architectures",
    "one architecture that rejects the current paradigm",
    "one architecture imported from an unrelated discipline",
    "one radically simplified architecture",
    "one conventional-software alternative",
    "one do-nothing alternative",
)

_ADVERSARIAL_OBLIGATIONS = (
    "strongest failure mode",
    "hidden governing assumption",
    "expected computational and operating cost",
    "best simpler competitor",
    "cheapest disconfirming experiment",
    "kill condition",
)

_INTEGRATION_OUTPUTS = (
    "mechanism anatomy record",
    "capability genome proposal",
    "typed interfaces and state variables",
    "authority envelope",
    "acceptance and adversarial tests",
    "failure and recovery conditions",
    "repository placement",
)


def build_invention_packet(
    request: WorkRequest,
    decision: RoutingDecision,
) -> InventionPacket:
    """Compile the exact proposal-only packet sent to the novelty model."""

    if decision.refused:
        raise RoutingError("cannot build an invention packet from a refused route")
    novelty_steps = [
        step for step in decision.steps if step.role == CognitiveRole.NOVELTY_ARCHITECT
    ]
    if len(novelty_steps) != 1:
        raise RoutingError("an invention packet requires exactly one novelty architect")

    payload = {
        "request_id": request.request_id,
        "model_id": novelty_steps[0].model_id,
        "intent_ref": request.intent.intent_ref,
        "objective": request.objective,
        "contradiction": request.intent.unresolved_contradiction,
        "routes": _REQUIRED_NOVELTY_ROUTES,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    return InventionPacket(
        packet_id=f"sha256:{digest}",
        request_id=request.request_id,
        assigned_model_id=novelty_steps[0].model_id,
        founder_intent_ref=request.intent.intent_ref,
        objective=request.objective,
        current_architecture_refs=request.intent.current_architecture_refs,
        protected_invariants=request.intent.protected_invariants,
        unresolved_contradiction=request.intent.unresolved_contradiction,
        required_routes=_REQUIRED_NOVELTY_ROUTES,
        adversarial_obligations=_ADVERSARIAL_OBLIGATIONS,
        integration_outputs=_INTEGRATION_OUTPUTS,
    )
