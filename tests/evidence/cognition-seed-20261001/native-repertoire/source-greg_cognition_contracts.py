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
    UNKNOWN = "unknown"
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


class ProofClass(StrEnum):
    EVIDENCE = "evidence_binding"
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
    FLOW = "flow_certificate"
    LINEAR = "linear_program_certificate"


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
    exposure_details: dict = field(default_factory=dict)

    def __post_init__(self):
        for name, value in asdict(self).items():
            if name == "exposure_details":
                strict_data(value)
                continue
            if name in ("lawful", "consent"):
                if value is not None and type(value) is not bool:
                    raise CognitionError(f"{name} must be boolean or unknown")
            else:
                number(value, low=0, high=1)

    @property
    def high(self):
        return any(v >= .5 for k, v in asdict(self).items() if k not in ("lawful", "consent", "exposure_details"))

    @property
    def prohibited(self):
        return self.lawful is False or self.consent is False or self.rights > 0 or self.discrimination > 0


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
    classification_uncertainty: float = 0.0
    unknown_geometry: bool = False
    out_of_distribution: bool = False
    success_criteria: tuple = ()
    failure_criteria: tuple = ()
    subclaims: tuple = ()
    assumptions: tuple = ()
    omitted_conditions: tuple = ()
    data_provenance: tuple = ()
    data_missingness: str = "unknown"
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
        for name in ("semantic_ambiguity", "constraint_density", "adversariality", "evidence_quality", "classification_uncertainty"):
            number(getattr(self, name), low=0, high=1)
        number(self.time_horizon, low=0)
        number(self.latency_limit, low=.01, high=30)
        number(self.financial_limit, low=0, high=0)  # these implementations never purchase cognition
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
    owner: str = "Kernel capability maintainers; Alfonso root authority"
    implementation_ref: str = "greg/cognition/solvers.py"
    competence_limits: str = "bounded declarative native workload only; not general field mastery"
    permission_limits: str = "current enclosing canonical mission grant; competence creates no rights"
    resource_fit: str = "two isolated CPU processes, 2 GiB worker ceiling, local model measured separately"
    license_evidence: str = "tests/evidence/cognition-seed-20261001/dependencies.json"
    export_import: str = "retained canonical journal and existing body restoration; no authority resurrection"
    recovery: str = "existing mission reconciliation; detached/revoked grants remain ineffective"

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
    "evidence_binding": ("claim", "sources", "bindings", "contradictions", "limitations"),
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
    "flow_certificate": ("model", "source_model", "input_digest", "flow", "solver_version", "limits"),
    "linear_program_certificate": ("model", "input_digest", "objective", "constraints", "claim", "solver_status", "solver_version", "limits", "bound", "gap", "infeasibility_certificate"),
}

# Payload schema rules only; executable method metadata remains in the existing
# catalog, reused lazily when a receipt is validated after module loading.
SEED_ARTIFACT_TYPES = {
    "evidence_binding": {"claim": str, "sources": list, "bindings": list, "contradictions": list, "limitations": list},
    "exact_calculation": {"expression": (str, dict), "result": dict},
    "formal_model": {"model": dict, "constraints": list, "solver_version": str, "solver_status": str, "reverse_translation": list},
    "optimization_certificate": {"objective": dict, "constraints": list, "solution": dict, "solver_status": str, "bound": (int, float, type(None))},
    "bounded_estimate": {"decomposition": list, "assumptions": list, "range": dict, "sensitivity": dict, "dominant_variable": str},
    "causal_identification": {"dag": list, "identification_assumptions": list, "estimand": str, "estimate": (int, float, type(None)), "confounders": list, "refutations": dict},
    "sourced_claims": {"sources": list, "claims": list, "contradictions": list, "uncertainty": str},
    "flow_certificate": {"model": dict, "source_model": dict, "input_digest": str, "flow": dict, "solver_version": str, "limits": str},
    "linear_program_certificate": {"model": dict, "input_digest": str, "objective": dict, "constraints": list, "claim": dict, "solver_status": str, "solver_version": str, "limits": dict, "bound": (int, float, type(None)), "gap": (int, float, type(None)), "infeasibility_certificate": type(None)},
    "posterior": {"prior": dict, "likelihood": str, "posterior": dict, "sensitivity": dict, "calibration": str},
    "control_trace": {"target": (int, float), "error": (int, float), "correction": (int, float), "state": dict, "stability_limit": str},
    "information_value": {"prior": (int, float), "posterior_scenarios": list, "expected_value": (int, float), "cost": (int, float)},
    "simulation_trace": {"model": str, "seed": int, "scenarios": list, "model_validity": str},
    "pattern_evidence": {"observations": list, "model": (str, dict), "scores": list, "limits": str},
    "search_trace": {"states": list, "path": list, "cost": (int, float, type(None)), "model": dict},
}


@dataclass(frozen=True)
class ProofArtifact:
    proof_class: str
    payload: dict

    def validate(self):
        required = PROOF_FIELDS.get(self.proof_class)
        if not isinstance(self.payload, dict) or not required or any(key not in self.payload for key in required):
            raise CognitionError("proof artifact does not satisfy its epistemic contract")
        for name, expected in SEED_ARTIFACT_TYPES.get(self.proof_class, {}).items():
            allowed = expected if isinstance(expected, tuple) else (expected,)
            if type(self.payload[name]) not in allowed:
                raise CognitionError(f"proof field {name} has the wrong type")
        statuses = {"formal_model": {"SAT", "UNSAT", "UNKNOWN"},
                    "optimization_certificate": {"OPTIMAL", "FEASIBLE", "INFEASIBLE", "MODEL_INVALID", "UNKNOWN"},
                    "linear_program_certificate": {"OPTIMAL", "FEASIBLE", "INFEASIBLE", "UNBOUNDED", "ABNORMAL", "MODEL_INVALID", "NOT_SOLVED"}}
        if self.proof_class in statuses and self.payload["solver_status"] not in statuses[self.proof_class]:
            raise CognitionError("unsupported native solver status")
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
    schema_version: str = "greg-cognition/0.2"
    policy_version: str = "seed-static/0.2"
    execution_mode: str = "consequence_inert"
    reason_code: str | None = None
    outcome_state: str = "ANSWERED_WITHIN_SCOPE"
    model_provenance: dict | None = None
    stopping_reason: str = "smallest sufficient bounded calculation; mandatory verification retained"
    formalization_coverage: dict = field(default_factory=dict)
    authority_refs: dict = field(default_factory=lambda: {"scope": "enclosing canonical Kernel witness/grant/receipt", "new_authority": False})
    contribution_attribution: list = field(default_factory=list)
    advantage_case: dict | None = None
    selective_disclosure: dict | None = None

    def __post_init__(self):
        EpistemicClass(self.epistemic_class)
        AbstentionClass(self.abstention_state)
        geometry = ProblemGeometry(**self.geometry)
        if geometry.epistemic_class != self.epistemic_class or geometry.consequence_class != self.consequence_class:
            raise CognitionError("receipt geometry and claim classification disagree")
        ConsequenceVector(**self.consequence_vector)
        number(self.money_cost, low=0, high=0)
        number(self.latency, low=0)
        if self.authority_created is not False or self.legitimate_authority != "EXISTING_KERNEL_GATE_REQUIRED":
            raise CognitionError("a cognitive receipt cannot create authority")
        if self.empirical_validity != "WORLD_UNVERIFIED":
            raise CognitionError("these bounded solvers cannot certify world validity")
        if self.proof_type is not None:
            from .catalog import FAMILIES
            family = self.method.removeprefix("cognition.") if isinstance(self.method, str) else None
            metadata = FAMILIES.get(family) if isinstance(self.method, str) and self.method.startswith("cognition.") else None
            expected = metadata[3] if metadata else None
            if expected != self.proof_type:
                raise CognitionError("receipt method and proof class disagree")
            if self.epistemic_class not in metadata[2]:
                raise CognitionError("proof class cannot establish this epistemic claim")
            ProofArtifact(self.proof_type, self.proof_artifact).validate()
            artifact, output = self.proof_artifact, self.output
            if not isinstance(output, dict):
                raise CognitionError("proof artifact requires its bounded output")
            # Bind the exported artifact to the result it accompanies. Numeric
            # truth and original-input checks remain the independent verifier's
            # job; this envelope prevents a verified result carrying another proof.
            coherent = True
            if self.proof_type == "exact_calculation":
                coherent = artifact["result"] == output
            elif self.proof_type == "bounded_estimate":
                coherent = artifact["range"] == output
            elif self.proof_type == "causal_identification":
                coherent = artifact["estimate"] == output.get("effect")
                if "uncertainty" in artifact:
                    coherent &= artifact["uncertainty"] == output.get("uncertainty")
            elif self.proof_type == "sourced_claims":
                coherent = artifact["claims"] == output.get("claims")
            elif self.proof_type in ("formal_model", "optimization_certificate"):
                coherent = artifact["solver_status"] == output.get("solver_status")
                if self.proof_type == "optimization_certificate":
                    coherent &= artifact["solution"] == output.get("solution")
            elif self.proof_type == "evidence_binding":
                coherent = artifact["claim"] == output.get("claim")
            elif self.proof_type == "search_trace" and family in ("graph", "search"):
                coherent = artifact["path"] == output.get("path") and artifact["cost"] == output.get("cost")
            elif self.proof_type == "flow_certificate":
                coherent = artifact["flow"] == output
            elif self.proof_type == "linear_program_certificate":
                coherent = artifact["solver_status"] == output.get("solver_status")
                if artifact["solver_status"] == "OPTIMAL":
                    coherent &= dict(zip(artifact["model"]["names"], artifact["claim"].get("x", []))) == output.get("solution")
            # Retain explicitly refuted artifacts for challenge/correction; they
            # cannot be consumed as an answered result or settled as competence.
            refuted = self.abstention_state == "REFUTED" and self.evaluator_result.get("verdict") == "REFUTED"
            if not coherent and not refuted:
                raise CognitionError("receipt artifact and output disagree")
        elif self.proof_artifact is not None:
            raise CognitionError("proof artifact requires its typed proof class")
        elif isinstance(self.method, str) and self.method.startswith("cognition.") and self.output is not None:
            raise CognitionError("native cognitive output requires its proof artifact")
        if self.advantage_case is not None or self.selective_disclosure is not None:
            if not isinstance(self.advantage_case, dict) or not isinstance(self.selective_disclosure, dict):
                raise CognitionError("proposal review requires its case and pointer-only disclosure package")
            from .advantage import validate_review
            validate_review(self.advantage_case, self.selective_disclosure, input_digest=self.input_digest)
            if self.selective_disclosure["formal_result"]["proof_type"] != self.proof_type or self.selective_disclosure["formal_result"]["artifact_ref"] != (digest(self.proof_artifact) if self.proof_artifact else None):
                raise CognitionError("disclosed proof pointer and receipt artifact disagree")
        retained_data(asdict(self))

    def to_dict(self):
        value = asdict(self)
        # Optional review metadata does not alter old receipt serialization.
        for name in ("advantage_case", "selective_disclosure"):
            if value[name] is None:
                value.pop(name)
        value["receipt_id"] = digest(value)
        return value
