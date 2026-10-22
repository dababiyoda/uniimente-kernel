"""Typed cognitive contracts. Assertions and integrity hashes are not authority."""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

from capabilities.genome import CONSEQUENCE_CLASSES
from egregore.contracts import ContractError, canonical_copy, canonical_json, digest, require_hash, require_text


class EpistemicClass(str, Enum):
    SEMANTIC = "semantic"
    ESTIMATE = "estimate"
    FORMAL = "formal"
    FACTUAL = "factual"
    CAUSAL = "causal"
    NORMATIVE = "normative"
    LEGAL = "legal"
    ARITHMETIC = "arithmetic"
    OPTIMIZATION = "optimization"
    PREDICTION = "prediction"
    PROBABILISTIC = "probabilistic"
    STRATEGIC = "strategic"
    PHYSICAL = "physical"
    INSTITUTIONAL = "institutional_acceptance"
    CONTROL = "control"
    SEARCH = "search"
    UNKNOWN = "unknown"


class ResultStatus(str, Enum):
    ANSWERED = "answered"
    ABSTAIN = "abstain"
    NEED_EVIDENCE = "need_evidence"
    HUMAN_REVIEW = "human_review"
    UNKNOWN = "unknown"


LAYERS = ("primitive_basal", "distributed_collective", "solver_macro_cognitive",
          "developmental_morphogenetic", "meta_intelligence")
HARM_DIMENSIONS = ("physical", "financial", "rights", "privacy", "reputation",
                   "discrimination", "third_party", "irreversible_disclosure",
                   "systemic", "tail_risk")
GATE_NAMES = ("law", "rights", "authorization", "evidence", "harm", "consent")


def finite_nonnegative(name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ContractError(f"{name} must be numeric")
    if not math.isfinite(value) or value < 0:
        raise ContractError(f"{name} must be finite and nonnegative")
    return float(value)


def text_tuple(name: str, value: Any) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ContractError(f"{name} must be a sequence")
    return tuple(require_text(name, x) for x in value)


def bounded_json_size(value, max_bytes=128 * 1024):
    """Check source material before copying; bound traversal, depth and bytes."""
    remaining, nodes = max_bytes, 0
    def visit(item, depth=0):
        nonlocal remaining, nodes
        nodes += 1
        if depth > 32 or nodes > 16384:
            raise ContractError("JSON material exceeds structural bounds")
        if isinstance(item, str):
            if len(item) > max_bytes:
                raise ContractError("JSON material exceeds byte ceiling")
            remaining -= len(item.encode("utf-8")) + 2
        elif isinstance(item, dict):
            remaining -= 2
            for key, child in item.items():
                if not isinstance(key, str):
                    raise ContractError("JSON object keys must be strings")
                visit(key, depth + 1)
                visit(child, depth + 1)
        elif isinstance(item, (list, tuple)):
            remaining -= 2
            for child in item:
                visit(child, depth + 1)
        elif item is None or isinstance(item, (int, float, bool)):
            remaining -= len(str(item)) + 1
        else:
            raise ContractError("unsupported JSON material")
        if remaining < 0:
            raise ContractError("JSON material exceeds byte ceiling")
    visit(value)
    encoded = len(canonical_json(value).encode("utf-8"))
    if encoded > max_bytes:
        raise ContractError("JSON material exceeds byte ceiling")
    return encoded


@dataclass(frozen=True)
class ProblemGeometry:
    epistemic_class: EpistemicClass = EpistemicClass.UNKNOWN
    objective_type: str = "analyse"
    features: dict = field(default_factory=dict)
    unresolved: tuple[str, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "epistemic_class", EpistemicClass(self.epistemic_class))
        require_text("objective_type", self.objective_type)
        if not isinstance(self.features, dict):
            raise ContractError("geometry features must be an object")
        bounded_json_size(self.features)
        object.__setattr__(self, "features", canonical_copy(self.features))
        object.__setattr__(self, "unresolved", text_tuple("unresolved", self.unresolved))

    def to_dict(self):
        return canonical_copy(asdict(self))

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict):
            raise ContractError("geometry must be an object")
        return cls(**value)


@dataclass(frozen=True)
class ConsequenceVector:
    consequence_class: str = "read_only"
    reversibility: str = "reversible"
    harms: dict[str, float | None] = field(default_factory=dict)
    rights_impact: bool = False

    def __post_init__(self):
        if self.consequence_class not in CONSEQUENCE_CLASSES:
            raise ContractError("unknown consequence class")
        if self.reversibility not in ("reversible", "partly_reversible", "irreversible", "unknown"):
            raise ContractError("unknown reversibility")
        if type(self.rights_impact) is not bool or not isinstance(self.harms, dict):
            raise ContractError("invalid consequence vector")
        if set(self.harms) - set(HARM_DIMENSIONS):
            raise ContractError("unknown harm dimension")
        values = {name: self.harms.get(name) for name in HARM_DIMENSIONS}
        for name, value in values.items():
            if value is not None:
                values[name] = finite_nonnegative(name, value)
        object.__setattr__(self, "harms", values)

    def to_dict(self):
        return canonical_copy(asdict(self))


@dataclass(frozen=True)
class CognitiveBudget:
    max_model_calls: int = 1
    max_cost_usd: float = 0.0
    max_latency_ms: int = 5000

    def __post_init__(self):
        if type(self.max_model_calls) is not int or not 0 <= self.max_model_calls <= 100:
            raise ContractError("max_model_calls must be an integer from 0 to 100")
        finite_nonnegative("max_cost_usd", self.max_cost_usd)
        if type(self.max_latency_ms) is not int or not 1 <= self.max_latency_ms <= 300000:
            raise ContractError("latency must be an integer from 1 to 300000 ms")


@dataclass(frozen=True)
class CognitiveRequest:
    problem_id: str
    question: str
    geometry: ProblemGeometry
    payload: dict = field(default_factory=dict)
    evidence_refs: tuple[str, ...] = ()
    consequence: ConsequenceVector = field(default_factory=ConsequenceVector)
    budget: CognitiveBudget = field(default_factory=CognitiveBudget)

    def __post_init__(self):
        require_text("problem_id", self.problem_id)
        require_text("question", self.question)
        if not isinstance(self.geometry, ProblemGeometry) or not isinstance(self.consequence, ConsequenceVector):
            raise ContractError("typed geometry and consequence required")
        if not isinstance(self.budget, CognitiveBudget) or not isinstance(self.payload, dict):
            raise ContractError("typed budget and object payload required")
        refs = text_tuple("evidence_refs", self.evidence_refs)
        if len(refs) > 64:
            raise ContractError("at most 64 evidence references")
        for ref in refs:
            require_hash("evidence_ref", ref)
        if len(set(refs)) != len(refs):
            raise ContractError("duplicate evidence reference")
        object.__setattr__(self, "evidence_refs", refs)
        bounded_json_size(self.payload)
        object.__setattr__(self, "payload", canonical_copy(self.payload))
        if len(canonical_json(self.to_dict()).encode()) > 128 * 1024:
            raise ContractError("cognitive input exceeds 128 KiB")

    def to_dict(self):
        return canonical_copy(asdict(self))

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict):
            raise ContractError("request must be an object")
        bounded_json_size(value)
        data = canonical_copy(value)
        data["geometry"] = ProblemGeometry.from_dict(data.get("geometry", {}))
        data["consequence"] = ConsequenceVector(**data.get("consequence", {}))
        data["budget"] = CognitiveBudget(**data.get("budget", {}))
        data["evidence_refs"] = tuple(data.get("evidence_refs", ()))
        return cls(**data)


@dataclass(frozen=True)
class GateAssessment:
    """Advisory eligibility supplied by the existing policy/domain owner.

    Passing this object authorizes neither execution nor activation. An evidence
    hash alone does not authenticate its evaluator or certify applicable law.
    """
    checks: dict[str, str]
    policy_ref: str
    policy_verdict: str
    missing: tuple[str, ...] = ()
    synthetic: bool = False

    def __post_init__(self):
        require_text("policy_ref", self.policy_ref)
        if self.policy_verdict not in ("allow", "deny", "require_human"):
            raise ContractError("unknown policy verdict")
        if not isinstance(self.checks, dict) or set(self.checks) != set(GATE_NAMES):
            raise ContractError("all eligibility gates must be explicit")
        if any(v not in ("pass", "fail", "unknown", "not_applicable") for v in self.checks.values()):
            raise ContractError("unknown gate state")
        if any(self.checks[k] == "not_applicable" for k in GATE_NAMES if k != "consent"):
            raise ContractError("only consent may be explicitly not applicable")
        if type(self.synthetic) is not bool:
            raise ContractError("synthetic must be boolean")
        object.__setattr__(self, "checks", canonical_copy(self.checks))
        object.__setattr__(self, "missing", text_tuple("missing", self.missing))

    @property
    def eligible(self):
        return (self.policy_verdict == "allow" and not self.missing
                and all(v in ("pass", "not_applicable") for v in self.checks.values()))

    def to_dict(self):
        return {**canonical_copy(asdict(self)), "advisory_only": True, "authority_created": False}

    @classmethod
    def from_dict(cls, value):
        data = dict(value)
        data.pop("advisory_only", None)
        data.pop("authority_created", None)
        return cls(**data)


@dataclass(frozen=True)
class ProofArtifact:
    kind: str
    data: dict
    assumptions: tuple[str, ...] = ()
    formal_validity: str = "not_applicable"
    empirical_validity: str = "world_unverified"

    def __post_init__(self):
        require_text("proof kind", self.kind)
        if not isinstance(self.data, dict):
            raise ContractError("proof data must be an object")
        if self.formal_validity not in ("not_applicable", "unknown", "valid_within_encoded_model"):
            raise ContractError("unknown formal-validity state")
        if self.empirical_validity != "world_unverified":
            raise ContractError("seed proofs cannot establish empirical finality")
        bounded_json_size(self.data, max_bytes=1024 * 1024)
        object.__setattr__(self, "data", canonical_copy(self.data))
        object.__setattr__(self, "assumptions", text_tuple("assumptions", self.assumptions))

    def to_dict(self):
        return canonical_copy(asdict(self))


@dataclass(frozen=True)
class CognitiveResult:
    method: str
    epistemic_class: EpistemicClass
    status: ResultStatus
    output: dict
    proof: ProofArtifact
    uncertainty: dict = field(default_factory=dict)
    missing_information: tuple[str, ...] = ()
    failure_modes: tuple[str, ...] = ()

    def __post_init__(self):
        require_text("method", self.method)
        object.__setattr__(self, "epistemic_class", EpistemicClass(self.epistemic_class))
        object.__setattr__(self, "status", ResultStatus(self.status))
        if not isinstance(self.proof, ProofArtifact) or not isinstance(self.output, dict):
            raise ContractError("typed proof and output object required")
        object.__setattr__(self, "output", canonical_copy(self.output))
        object.__setattr__(self, "uncertainty", canonical_copy(self.uncertainty))
        object.__setattr__(self, "missing_information", text_tuple("missing_information", self.missing_information))
        object.__setattr__(self, "failure_modes", text_tuple("failure_modes", self.failure_modes))

    def to_dict(self):
        return canonical_copy(asdict(self))


@dataclass(frozen=True)
class VerificationResult:
    accepted: bool
    findings: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    coverage: tuple[str, ...] = ()

    def __post_init__(self):
        if type(self.accepted) is not bool:
            raise ContractError("verifier accepted must be boolean")
        for name in ("findings", "dependencies", "coverage"):
            object.__setattr__(self, name, text_tuple(name, getattr(self, name)))

    def to_dict(self):
        return canonical_copy(asdict(self))


@dataclass(frozen=True)
class CognitiveReceipt:
    receipt_id: str
    problem_id: str
    input_digest: str
    geometry: dict
    consequence: dict
    gates: dict
    selected_method: str | None
    alternative_methods_considered: tuple[str, ...]
    method_selection_reason: str
    result: CognitiveResult
    verification: VerificationResult
    resource_usage: dict
    latency_ms: float
    evidence_refs: tuple[str, ...]
    disposition: str
    method_version: str = "0.1.0"
    later_outcome: str = "unresolved"
    request_ref: str | None = None

    def __post_init__(self):
        for name in ("geometry", "consequence", "gates", "resource_usage"):
            if not isinstance(getattr(self, name), dict):
                raise ContractError(f"receipt {name} must be an object")
            object.__setattr__(self, name, canonical_copy(getattr(self, name)))
        for name in ("alternative_methods_considered", "evidence_refs"):
            object.__setattr__(self, name, text_tuple(name, getattr(self, name)))
        require_hash("receipt_id", self.receipt_id)
        require_hash("input_digest", self.input_digest)
        if self.request_ref is not None:
            require_hash("request_ref", self.request_ref)
        if self.disposition not in ("recommend", "abstain", "test", "handoff"):
            raise ContractError("unknown receipt disposition")

    @property
    def execution_authority(self):
        return "none"

    def to_dict(self):
        return {**canonical_copy(asdict(self)), "authority_created": False,
                "legitimate_authority": "not_granted", "execution_authority": "none"}

    @classmethod
    def from_dict(cls, value):
        data = canonical_copy(value)
        for key in ("authority_created", "legitimate_authority", "execution_authority"):
            data.pop(key, None)
        result = dict(data["result"])
        result["proof"] = ProofArtifact(**result["proof"])
        data["result"] = CognitiveResult(**result)
        data["verification"] = VerificationResult(**data["verification"])
        data["alternative_methods_considered"] = tuple(data["alternative_methods_considered"])
        data["evidence_refs"] = tuple(data["evidence_refs"])
        return cls(**data)
