"""Epistemic contracts. Formal validity, world validity and authority are independent."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
import hashlib
import json
import math


class CognitionError(ValueError):
    pass


class EpistemicClass(StrEnum):
    DEDUCTIVE = "deductive"
    ARITHMETIC = "arithmetic"
    FEASIBILITY = "constraint_feasibility"
    OPTIMIZATION = "optimization"
    ESTIMATE = "estimate"
    PREDICTION = "prediction"
    CAUSAL = "causal"
    SEMANTIC = "semantic"
    STRATEGIC = "strategic"
    NORMATIVE = "normative"
    LEGAL = "legal"
    PHYSICAL = "physical"
    INSTITUTIONAL = "institutional_acceptance"
    # Additive (cortex bridge): classification failed. Never coerced to another class.
    UNRESOLVED = "unresolved"


class ProofClass(StrEnum):
    EXACT = "exact_calculation"
    FORMAL = "formal_model"
    OPTIMIZATION = "optimization_certificate"
    ESTIMATE = "bounded_estimate"
    BAYESIAN = "posterior"
    CAUSAL = "causal_identification"
    SEMANTIC = "sourced_claims"
    SEARCH = "search_trace"
    CONTROL = "control_trace"
    INFORMATION = "information_value"
    SIMULATION = "simulation_trace"
    GAME = "game_model"
    HUMAN = "human_judgment"
    PATTERN = "pattern_evidence"
    COLLECTIVE = "collective_trace"
    # Additive (cortex bridge): the complete cortex receipt, itself a typed union of
    # formal / optimization / estimation / evidence / causal / semantic / deterrence proofs.
    CORTEX = "cortex_receipt"


class AbstentionClass(StrEnum):
    NONE = "NONE"
    ABSTAIN = "ABSTAIN"
    PROHIBITED = "PROHIBITED"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
    CAPABILITY_DEFICIT = "CAPABILITY_DEFICIT"
    EVIDENCE_EXPIRED = "EVIDENCE_EXPIRED"
    FORMALIZATION_INCOMPLETE = "FORMALIZATION_INCOMPLETE"
    WORLD_UNVERIFIED = "WORLD_UNVERIFIED"
    REFUTED = "REFUTED"
    UNKNOWN = "UNKNOWN"
    UNIDENTIFIED = "UNIDENTIFIED"
    NO_QUORUM = "NO_QUORUM"


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def digest(value) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode()).hexdigest()


def number(value, *, low=-1e12, high=1e12) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise CognitionError(f"finite number in [{low}, {high}] required")
    return value


def integer(value, *, low=0, high=10000) -> int:
    if type(value) is not int or not low <= value <= high:
        raise CognitionError(f"integer in [{low}, {high}] required")
    return value


def strict_data(value, *, depth=0):
    if depth > 16:
        raise CognitionError("input nesting exceeds 16")
    if isinstance(value, dict):
        if len(value) > 1000 or any(not isinstance(k, str) for k in value):
            raise CognitionError("bounded string-keyed data required")
        for v in value.values():
            strict_data(v, depth=depth + 1)
    elif isinstance(value, list):
        if len(value) > 10000:
            raise CognitionError("input list exceeds 10000")
        for v in value:
            strict_data(v, depth=depth + 1)
    elif type(value) in (int, float):
        number(value)
    elif value is not None and type(value) not in (str, bool):
        raise CognitionError("JSON data required")


def retained_data(value):
    """Fit existing AuthorityOffice retention bounds without mutating receipt bytes."""
    if isinstance(value, dict):
        for v in value.values():
            retained_data(v)
    elif isinstance(value, list):
        if len(value) > 1000:
            raise CognitionError("proof exceeds canonical receipt retention; subdivide the problem")
        for v in value:
            retained_data(v)
    elif isinstance(value, str) and len(value) > 16 * 1024:
        raise CognitionError("proof text exceeds canonical receipt retention; use bounded source references")


@dataclass(frozen=True)
class ConsequenceVector:
    physical: float = 0.0
    financial: float = 0.0
    privacy: float = 0.0
    rights: float = 0.0
    reputation: float = 0.0
    innocent_third_party: float = 0.0
    irreversibility: float = 0.0
    disclosure: float = 0.0
    dependency: float = 0.0
    systemic_externality: float = 0.0
    tail_risk: float = 0.0
    discrimination: float = 0.0
    lawful: bool | None = None
    consent: bool | None = None

    def __post_init__(self):
        for name, value in asdict(self).items():
            if name in ("lawful", "consent"):
                if value is not None and type(value) is not bool:
                    raise CognitionError(f"{name} must be boolean or unknown")
            elif value is not None:   # None = not measured; unknown is never coerced to zero
                number(value, low=0, high=1)

    @property
    def unknown(self):
        return tuple(k for k, v in asdict(self).items() if v is None and k not in ("lawful", "consent"))

    @property
    def high(self):
        return any(v is not None and v >= .5 for k, v in asdict(self).items() if k not in ("lawful", "consent"))

    @property
    def prohibited(self):
        return (self.lawful is False or self.consent is False or (self.rights or 0) > 0
                or (self.discrimination or 0) > 0)


@dataclass(frozen=True)
class ProblemGeometry:
    objective_type: str = "answer"
    domain: str = "bounded_computation"
    epistemic_class: str = "semantic"
    semantic_ambiguity: float = 0.0
    exactness_required: bool = False
    deterministic: bool = True
    stochastic: bool = False
    partially_observed: bool = False
    static_or_sequential: str = "static"
    discrete_or_continuous: str = "discrete"
    graph_structure: bool = False
    constraint_density: float = 0.0
    search_space_size: int = 0
    causal_question: bool = False
    forecasting_question: bool = False
    optimization_question: bool = False
    control_question: bool = False
    allocation_question: bool = False
    adversariality: float = 0.0
    multi_actor: bool = False
    incentive_interaction: bool = False
    data_volume: int = 0
    evidence_quality: float = 0.0
    identifiability: str = "unknown"
    novelty_requirement: bool = False
    embodiment_requirement: bool = False
    time_horizon: float = 0.0
    latency_limit: float = 5.0
    compute_limit: int = 10000
    financial_limit: float = 0.0
    consequence_class: str = "read_only"
    reversibility: str = "reversible"
    rights_impact: bool = False
    legal_content: bool = False
    human_value_content: bool = False
    deadline: str | None = None
    attention_ceiling_seconds: float = 0.0

    def __post_init__(self):
        EpistemicClass(self.epistemic_class)
        for name, spec in self.__dataclass_fields__.items():
            if isinstance(spec.default, bool) and type(getattr(self, name)) is not bool:
                raise CognitionError(f"{name} must be boolean")
            if isinstance(spec.default, str) and (not isinstance(getattr(self, name), str) or
                                                 not 1 <= len(getattr(self, name)) <= 128):
                raise CognitionError(f"{name} requires a bounded string")
        for name in ("semantic_ambiguity", "constraint_density", "adversariality", "evidence_quality"):
            number(getattr(self, name), low=0, high=1)
        number(self.time_horizon, low=0)
        number(self.latency_limit, low=.01, high=30)
        number(self.financial_limit, low=0, high=0)  # these implementations never purchase cognition
        number(self.attention_ceiling_seconds, low=0, high=86400)
        if self.deadline is not None:
            from datetime import datetime
            if not isinstance(self.deadline, str) or len(self.deadline) > 128:
                raise CognitionError("bounded offset-aware deadline required")
            try:
                instant = datetime.fromisoformat(self.deadline.replace("Z", "+00:00"))
            except ValueError as exc:
                raise CognitionError("invalid cognition deadline") from exc
            if instant.tzinfo is None:
                raise CognitionError("offset-aware deadline required")
        integer(self.compute_limit, low=1, high=100000)
        integer(self.search_space_size, high=1000000000)
        integer(self.data_volume, high=1000000)
        if self.consequence_class not in ("read_only", "internal_write", "external_contact", "financial", "irreversible"):
            raise CognitionError("unknown consequence class")
        if self.static_or_sequential not in ("static", "sequential") or self.discrete_or_continuous not in ("discrete", "continuous", "mixed"):
            raise CognitionError("invalid problem geometry")
        if self.identifiability not in ("unknown", "identified", "unidentified"):
            raise CognitionError("invalid identification state")
        if self.reversibility not in ("reversible", "partially_reversible", "irreversible", "unknown"):
            raise CognitionError("invalid reversibility")


@dataclass(frozen=True)
class CognitiveCapabilityProfile:
    family: str
    layer: int
    operations: tuple[str, ...]
    epistemic_classes: tuple[str, ...]
    proof_class: str
    deterministic: bool = True
    assumptions: tuple[str, ...] = ("Supplied model may omit material world conditions",)
    evidence_requirements: tuple[str, ...] = ("typed bounded input",)
    uncertainty_model: str = "conditional on input"
    state: str = "stateless; caller supplies bounded local state"
    memory: str = "canonical GREG journal only"
    update_rule: str = "verified outcomes alter per-geometry competence, never authority"
    cost_usd: float = 0.0
    latency_estimate_seconds: float = .01
    compute_ceiling: int = 100000
    energy: str = "unmeasured local CPU"
    competence_history: tuple[str, ...] = ()
    calibration_history: tuple[str, ...] = ()
    contraindications: tuple[str, ...] = ("unbounded or unsupported problem",)
    abstention_conditions: tuple[str, ...] = ("missing input, dependency, evidence or authority",)
    failure_modes: tuple[str, ...] = ("model mismatch", "timeout", "unknown")
    falsification_tests: tuple[str, ...] = ("tests/unit/test_greg_cognition.py",)
    authority_ceiling: str = "read_only"
    consequence_ceiling: str = "read_only"
    attach: str = "existing CapabilityRegistry and signed mission scope"
    detach: str = "existing founder CAPABILITY_DETACH"
    rollback: str = "detach, retain canonical receipts"
    shutdown: str = "bounded worker termination; existing body stop always wins"
    lineage: tuple[str, ...] = ("INTENT-20260930-polyintelligence",)

    def validate(self):
        if not self.family or not self.operations or not self.lineage:
            raise CognitionError("profile requires family, operations and lineage")
        integer(self.layer, low=1, high=5)
        for cls in self.epistemic_classes:
            EpistemicClass(cls)
        ProofClass(self.proof_class)
        number(self.cost_usd, low=0, high=0)
        number(self.latency_estimate_seconds, low=0, high=30)
        integer(self.compute_ceiling, low=1, high=100000)
        if self.authority_ceiling != "read_only" or self.consequence_ceiling != "read_only":
            raise CognitionError("cognitive profiles cannot manufacture effect authority")

    @classmethod
    def from_dict(cls, data):
        profile = cls(**data)
        profile.validate()
        return profile


PROOF_FIELDS = {
    "exact_calculation": ("expression", "result"),
    "formal_model": ("model", "constraints", "solver_version", "solver_status", "reverse_translation"),
    "optimization_certificate": ("objective", "constraints", "solution", "solver_status", "bound"),
    "bounded_estimate": ("decomposition", "assumptions", "range", "sensitivity", "dominant_variable", "outside_view_anchor"),
    "posterior": ("prior", "likelihood", "posterior", "sensitivity", "calibration"),
    "causal_identification": ("dag", "identification_assumptions", "estimand", "estimate", "confounders", "refutations"),
    "sourced_claims": ("sources", "claims", "contradictions", "uncertainty"),
    "search_trace": ("states", "path", "cost", "model"),
    "control_trace": ("target", "error", "correction", "state", "stability_limit"),
    "information_value": ("prior", "posterior_scenarios", "expected_value", "cost"),
    "simulation_trace": ("model", "seed", "scenarios", "model_validity"),
    "game_model": ("payoffs", "strategies", "value", "constraints"),
    "human_judgment": ("participants", "expertise", "conflicts", "dissent", "decision_authority"),
    "pattern_evidence": ("observations", "model", "scores", "limits"),
    "collective_trace": ("participants", "independence", "dissent", "trace", "baseline_status"),
    "cortex_receipt": ("schema", "receipt_id", "geometry", "route", "verifier", "truth", "disposition",
                       "accountability", "outcome", "authority_created", "execution_authority"),
}


@dataclass(frozen=True)
class ProofArtifact:
    proof_class: str
    payload: dict

    def validate(self):
        required = PROOF_FIELDS.get(self.proof_class)
        if not required or any(key not in self.payload for key in required):
            raise CognitionError("proof artifact does not satisfy its epistemic contract")
        strict_data(self.payload)


@dataclass(frozen=True)
class CognitiveReceipt:
    problem_id: str
    geometry: dict
    consequence_class: str
    consequence_vector: dict
    method: str
    method_version: str
    epistemic_class: str
    input_digest: str
    evidence_refs: list
    assumptions: list
    excluded_variables: list
    output: dict | None
    uncertainty: dict
    proof_type: str | None
    proof_artifact: dict | None
    alternative_methods_considered: list
    method_selection_reason: str
    strongest_counterargument: str
    falsification_condition: str
    abstention_state: str
    missing_information: list
    compute_cost: dict
    money_cost: float
    latency: float
    evaluator: str
    evaluator_result: dict
    formal_validity: str = "NOT_APPLICABLE"
    empirical_validity: str = "WORLD_UNVERIFIED"
    legitimate_authority: str = "EXISTING_KERNEL_GATE_REQUIRED"
    later_outcome: dict | None = None
    calibration_error: float | None = None
    causal_credit: list = field(default_factory=list)
    authority_created: bool = False
    # Additive (directive section 6): the explicit outcome taxonomy and reasons, a pure
    # projection of abstention_state (or of the cortex receipt). Receipts retained before
    # this field existed remain valid without it.
    outcome: dict | None = None
    authority_refs: dict | None = None
    reason_code: str | None = None
    stopping_reason: str | None = None

    def __post_init__(self):
        EpistemicClass(self.epistemic_class)
        AbstentionClass(self.abstention_state)
        ProblemGeometry(**self.geometry)
        ConsequenceVector(**self.consequence_vector)
        number(self.money_cost, low=0, high=0)
        number(self.latency, low=0)
        if self.authority_created is not False or self.legitimate_authority != "EXISTING_KERNEL_GATE_REQUIRED":
            raise CognitionError("a cognitive receipt cannot create authority")
        if self.empirical_validity != "WORLD_UNVERIFIED":
            raise CognitionError("these bounded solvers cannot certify world validity")
        if self.authority_refs is not None:
            strict_data(self.authority_refs)
            if not isinstance(self.authority_refs, dict) or self.authority_refs.get("new_authority") is not False:
                raise CognitionError("budget projection cannot create authority")
        if self.proof_type is not None:
            ProofArtifact(self.proof_type, self.proof_artifact).validate()
        if self.outcome is not None:
            from cortex.outcomes import OUTCOMES, REASONS
            if (set(self.outcome) != {"outcome", "reasons", "taxonomy"} or self.outcome["outcome"] not in OUTCOMES
                    or not set(self.outcome["reasons"]) <= set(REASONS)):
                raise CognitionError("outcome must use the directive taxonomy")
        retained_data(asdict(self))

    def to_dict(self):
        value = asdict(self)
        for name in ("authority_refs", "reason_code", "stopping_reason"):
            if value[name] is None:
                value.pop(name)
        value["receipt_id"] = digest(value)
        return value
