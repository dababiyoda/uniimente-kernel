"""Shared cognitive contracts for the Polyintelligence Cortex seed (v0.1).

Doctrine (build prompt SEED-V0.1 items 2, 4, 8):

* Cognition proposes. It never authorizes. Every cortex output is a
  recommendation, an abstention, a bounded test or a handoff; external effects
  still pass only through the Kernel authority path and the Consequence Gate.
* Unknown is a value. A field that cannot be established is recorded as
  ``unknown`` and listed in ``unresolved_fields``; it is never silently
  defaulted to a convenient answer.
* A semantic model may *propose* geometry features. A proposal is kept with
  its confidence and is accepted only when the structured problem supports it.

This module is pure data and validation. It imports nothing that can act.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Any, Mapping

from capabilities.genome import CONSEQUENCE_CLASSES

CORTEX_VERSION = "0.1.0"


class CortexError(ValueError):
    """A cortex boundary object is malformed. Fails closed."""


# ------------------------------------------------------------------ hashing
def canonical_json(value: Any) -> str:
    """Sorted-key, compact, NaN-free JSON (same convention as egregore.contracts)."""
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise CortexError(f"value is not canonical JSON: {exc}") from exc


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


# ------------------------------------------------------------------ taxonomy
# Build prompt item 2: the five architectural layers. They are selectable
# scales and mechanisms, not five services and not a sequential pipeline.
LAYERS = (
    "primitive_basal",
    "distributed_collective",
    "solver_macro_cognitive",
    "developmental_morphogenetic",
    "meta_polyintelligence_cortex",
)
# The earlier review (docs/intent/sources/...REVIEW-PASS-1/2) named five
# layers differently. Both are preserved; this map is the reconciliation
# recorded as a conflict in the intent ledger, not a silent rename.
REVIEW_LAYER_MAP = {
    "L1_microintelligence": ("primitive_basal",),
    "L2_bounded_competency_cells": ("primitive_basal",),
    "L3_specialized_intelligence_organs": ("solver_macro_cognitive",),
    "L4_collective_and_developmental": ("distributed_collective", "developmental_morphogenetic"),
    "L5_metacognitive_institutional": ("meta_polyintelligence_cortex",),
}

# Review PASS-1 section 31, verbatim table rows, as identifiers.
EPISTEMIC_CLASSES = (
    "deductive_logical",         # formal proof / solver
    "arithmetic",                # exact calculation
    "constraint_feasibility",    # SMT/CP-SAT
    "optimization",              # OR/optimizer
    "estimate",                  # Fermi/probabilistic
    "prediction",                # statistical/Bayesian
    "causal",                    # causal inference/experiment
    "semantic",                  # model + sources
    "strategic",                 # branching + simulation + evidence
    "normative_value",           # legitimate human/policy authority
    "legal",                     # qualified legal evidence/human authority
    "physical_perceptual",       # sensors/measurements
    "institutional_acceptance",  # actual external actor behavior
)
# Classes whose final answer belongs to legitimate human or institutional
# authority. The cortex may assist; it hands off.
HUMAN_AUTHORITY_CLASSES = ("normative_value", "legal", "institutional_acceptance")

# Build prompt item 6: the Evidence/Causal route distinguishes these.
CLAIM_TYPES = ("factual_support", "association", "prediction", "intervention")
CLAIM_TYPE_TO_EPISTEMIC = {
    "factual_support": "semantic",
    "association": "prediction",
    "prediction": "prediction",
    "intervention": "causal",
}

PROOF_CLASSES = (
    # implemented in the seed
    "semantic_sourced", "estimation", "formal", "evidence_assessment",
    "causal_estimate", "gate_report", "verifier_findings",
    # reserved for registered-but-disabled families (no executor in v0.1)
    "optimization", "bayesian", "simulation", "human_adjudication",
    "measurement", "institutional_observation",
)
IMPLEMENTED_PROOF_CLASSES = PROOF_CLASSES[:7]

DISPOSITIONS = ("recommend", "abstain", "bounded_test", "handoff")

# Explicit states (build prompt item 7: incomplete formalization, unverified
# real-world premises, unavailable dependencies, timeouts, inconclusive).
STATES = (
    "OK",
    "FORMALIZATION_INCOMPLETE",
    "WORLD_UNVERIFIED",
    "DEPENDENCY_UNAVAILABLE",
    "TIMEOUT",
    "INCONCLUSIVE",
    "BUDGET_EXHAUSTED",
    "NOT_IDENTIFIED",
    "INSUFFICIENT_EVIDENCE",
    "CONTESTED",
    "MALFORMED_INPUT",
    "DIMENSION_MISMATCH",
    "UNSUPPORTED_GEOMETRY",
    "NO_ELIGIBLE_METHOD",
    "GATE_FAILED",
    "GATE_UNRESOLVED",
    "REQUIRES_HUMAN_AUTHORITY",
)

# Build prompt item 8: harm is a vector. Missing measurements remain unknown.
HARM_DIMENSIONS = (
    "physical", "financial", "rights", "privacy", "reputational",
    "discrimination", "third_party", "irreversible_disclosure", "systemic", "tail_risk",
)
# Dimensions where a high rating is a hard prohibition, never a cost.
HARD_HARM_DIMENSIONS = ("physical", "rights", "discrimination", "third_party", "irreversible_disclosure")
HARM_LEVELS = ("none", "low", "medium", "high", "critical", "unknown")

VICTIM_PROTECTION_ACTIONS = (
    "immediate_protection", "containment", "evidence_preservation", "safe_contact",
    "escalation", "restitution", "recurrence_prevention",
)
EVIDENCE_ACCESS = ("restricted", "need_to_know", "internal", "unknown")

LEVELS = ("none", "low", "medium", "high", "unknown")
EXACTNESS = ("exact_required", "approximate_ok", "unknown")
TEMPORAL = ("static", "sequential", "unknown")
REVERSIBILITY = ("reversible", "costly_to_reverse", "irreversible", "unknown")
CAUSAL_STRUCTURE = ("none", "declared_adjustment", "declared_experiment", "unidentified",
                    "model_generated", "unknown")
OBJECTIVES = ("decide_feasibility", "decide_entailment", "estimate_quantity", "assess_claim",
              "estimate_effect", "synthesize", "choose_option", "adjudicate", "unknown")

# Where a geometry value came from. Semantic proposals never count as
# established unless validated against the structured payload.
FIELD_SOURCES = ("payload_structure", "requester_declared", "semantic_proposal_validated",
                 "default_unknown")


def _enum(name: str, value: Any, allowed: tuple) -> str:
    if value not in allowed:
        raise CortexError(f"{name} must be one of {allowed}, got {value!r}")
    return value


def _text(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CortexError(f"{name} must be a non-empty string")
    return value


def _nonneg(name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise CortexError(f"{name} must be a finite non-negative number")
    return float(value)


def consequence_rank(consequence_class: str) -> int:
    _enum("consequence_class", consequence_class, CONSEQUENCE_CLASSES)
    return CONSEQUENCE_CLASSES.index(consequence_class)


# ------------------------------------------------------------------ consequence
@dataclass(frozen=True)
class ConsequenceVector:
    """Harm separated by dimension. A scalar harm score is not representable here."""

    levels: Mapping[str, str]

    @classmethod
    def from_partial(cls, values: Mapping[str, str] | None) -> "ConsequenceVector":
        values = dict(values or {})
        unknown_dims = set(values) - set(HARM_DIMENSIONS)
        if unknown_dims:
            raise CortexError(f"unknown harm dimensions: {sorted(unknown_dims)}")
        levels = {}
        for dim in HARM_DIMENSIONS:
            levels[dim] = _enum(f"harm.{dim}", values.get(dim, "unknown"), HARM_LEVELS)
        return cls(levels=levels)

    def unknown(self) -> tuple[str, ...]:
        return tuple(d for d in HARM_DIMENSIONS if self.levels[d] == "unknown")

    def hard_violations(self) -> tuple[str, ...]:
        """Hard dimensions at high/critical, plus any dimension at critical."""
        out = []
        for dim in HARM_DIMENSIONS:
            level = self.levels[dim]
            if level == "critical" or (dim in HARD_HARM_DIMENSIONS and level == "high"):
                out.append(dim)
        return tuple(out)

    def to_dict(self) -> dict:
        return dict(self.levels)


@dataclass(frozen=True)
class VictimProtection:
    """Build prompt item 8: distinguish protective actions; control evidence access."""

    relevant: bool
    required_actions: tuple[str, ...] = ()
    evidence_access: str = "unknown"
    disclosure_controls: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, value: Mapping[str, Any] | None) -> "VictimProtection":
        if not value:
            return cls(relevant=False)
        actions = tuple(value.get("required_actions", ()))
        for action in actions:
            _enum("victim_protection.action", action, VICTIM_PROTECTION_ACTIONS)
        access = _enum("victim_protection.evidence_access",
                       value.get("evidence_access", "unknown"), EVIDENCE_ACCESS)
        controls = tuple(value.get("disclosure_controls", ()))
        if bool(value.get("relevant", True)) and "evidence_preservation" in actions and access in ("unknown", "internal"):
            raise CortexError("preserved victim evidence requires restricted or need_to_know access")
        return cls(relevant=bool(value.get("relevant", True)), required_actions=actions,
                   evidence_access=access, disclosure_controls=controls)

    def to_dict(self) -> dict:
        return {"relevant": self.relevant, "required_actions": list(self.required_actions),
                "evidence_access": self.evidence_access,
                "disclosure_controls": list(self.disclosure_controls)}


# ------------------------------------------------------------------ problem
PAYLOAD_KEYS = ("formal_model", "estimation_model", "sources", "evidence", "claim",
                "causal_spec", "options", "declared", "resources", "as_of", "victim_protection",
                "faults")


@dataclass(frozen=True)
class Problem:
    """A question plus the structured facts available to answer it.

    Every fact the routed seed may use is in ``payload``. Baselines receive the
    same facts rendered as text in ``question`` (build prompt item 9:
    equivalent available facts).
    """

    problem_id: str
    question: str
    payload: Mapping[str, Any]

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Problem":
        if not isinstance(value, Mapping):
            raise CortexError("problem must be an object")
        pid = _text("problem_id", value.get("problem_id"))
        question = _text("question", value.get("question"))
        payload = value.get("payload", {})
        if not isinstance(payload, Mapping):
            raise CortexError("payload must be an object")
        extra = set(payload) - set(PAYLOAD_KEYS)
        if extra:
            raise CortexError(f"unknown payload keys: {sorted(extra)}")
        # Detach caller-owned objects and reject non-JSON values.
        payload = json.loads(canonical_json(dict(payload)))
        return cls(problem_id=pid, question=question, payload=payload)

    def to_dict(self) -> dict:
        return {"problem_id": self.problem_id, "question": self.question, "payload": dict(self.payload)}


# ------------------------------------------------------------------ geometry
@dataclass(frozen=True)
class ResourceLimits:
    max_cost_usd: float = 0.05
    max_latency_s: float = 30.0
    max_model_calls: int = 4
    max_solver_calls: int = 64

    @classmethod
    def from_dict(cls, value: Mapping[str, Any] | None) -> "ResourceLimits":
        value = dict(value or {})
        limits = cls(
            max_cost_usd=_nonneg("max_cost_usd", value.get("max_cost_usd", cls.max_cost_usd)),
            max_latency_s=_nonneg("max_latency_s", value.get("max_latency_s", cls.max_latency_s)),
            max_model_calls=int(_nonneg("max_model_calls", value.get("max_model_calls", cls.max_model_calls))),
            max_solver_calls=int(_nonneg("max_solver_calls", value.get("max_solver_calls", cls.max_solver_calls))),
        )
        return limits

    def to_dict(self) -> dict:
        return {"max_cost_usd": self.max_cost_usd, "max_latency_s": self.max_latency_s,
                "max_model_calls": self.max_model_calls, "max_solver_calls": self.max_solver_calls}


@dataclass(frozen=True)
class ProblemGeometry:
    """Build prompt item 4: the shape of a problem, with explicit unknowns."""

    problem_id: str
    epistemic_class: str | None
    claim_type: str | None
    objective: str
    ambiguity: str
    exactness: str
    uncertainty: str
    causal_structure: str
    constraints: tuple[str, ...]
    temporal_character: str
    evidence_quality: str
    resource_limits: ResourceLimits
    consequence_vector: ConsequenceVector
    consequence_class: str
    reversibility: str
    unresolved_fields: tuple[str, ...]
    provenance: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    rejected_proposals: tuple[Mapping[str, Any], ...] = ()

    def __post_init__(self):
        if self.epistemic_class is not None:
            _enum("epistemic_class", self.epistemic_class, EPISTEMIC_CLASSES)
        if self.claim_type is not None:
            _enum("claim_type", self.claim_type, CLAIM_TYPES)
        _enum("objective", self.objective, OBJECTIVES)
        _enum("ambiguity", self.ambiguity, LEVELS)
        _enum("exactness", self.exactness, EXACTNESS)
        _enum("uncertainty", self.uncertainty, LEVELS)
        _enum("causal_structure", self.causal_structure, CAUSAL_STRUCTURE)
        _enum("temporal_character", self.temporal_character, TEMPORAL)
        _enum("evidence_quality", self.evidence_quality, LEVELS)
        _enum("consequence_class", self.consequence_class, CONSEQUENCE_CLASSES)
        _enum("reversibility", self.reversibility, REVERSIBILITY)
        for name, meta in self.provenance.items():
            _enum(f"provenance.{name}.source", meta.get("source"), FIELD_SOURCES)

    def to_dict(self) -> dict:
        return {
            "problem_id": self.problem_id,
            "epistemic_class": self.epistemic_class,
            "claim_type": self.claim_type,
            "objective": self.objective,
            "ambiguity": self.ambiguity,
            "exactness": self.exactness,
            "uncertainty": self.uncertainty,
            "causal_structure": self.causal_structure,
            "constraints": list(self.constraints),
            "temporal_character": self.temporal_character,
            "evidence_quality": self.evidence_quality,
            "resource_limits": self.resource_limits.to_dict(),
            "consequence_vector": self.consequence_vector.to_dict(),
            "consequence_class": self.consequence_class,
            "reversibility": self.reversibility,
            "unresolved_fields": list(self.unresolved_fields),
            "provenance": {k: dict(v) for k, v in sorted(self.provenance.items())},
            "rejected_proposals": [dict(p) for p in self.rejected_proposals],
        }


# ------------------------------------------------------------------ organ result
@dataclass(frozen=True)
class Expenditure:
    usd: float = 0.0
    seconds: float = 0.0
    model_calls: int = 0
    solver_calls: int = 0

    def plus(self, other: "Expenditure") -> "Expenditure":
        return Expenditure(self.usd + other.usd, self.seconds + other.seconds,
                           self.model_calls + other.model_calls, self.solver_calls + other.solver_calls)

    def to_dict(self) -> dict:
        return {"usd": round(self.usd, 6), "seconds": round(self.seconds, 6),
                "model_calls": self.model_calls, "solver_calls": self.solver_calls}


ORIGINS = ("deterministic", "solver", "model_output", "human", "measurement")


@dataclass(frozen=True)
class OrganResult:
    """What one route returns. ``proof`` is a typed artifact (see cortex.proofs)."""

    organ_id: str
    organ_version: str
    state: str
    answer: Mapping[str, Any] | None
    proof: Mapping[str, Any]
    assumptions: tuple[str, ...] = ()
    uncertainty: str = "unknown"
    expenditure: Expenditure = field(default_factory=Expenditure)
    dependencies: tuple[str, ...] = ()
    origin: str = "deterministic"
    notes: tuple[str, ...] = ()

    def __post_init__(self):
        _enum("state", self.state, STATES)
        _enum("origin", self.origin, ORIGINS)
        _enum("proof.proof_class", self.proof.get("proof_class"), PROOF_CLASSES)
        if self.state != "OK" and self.answer is not None and self.state not in (
                "WORLD_UNVERIFIED", "CONTESTED", "INCONCLUSIVE"):
            raise CortexError(f"state {self.state} may not carry an answer")

    def to_dict(self) -> dict:
        return {"organ_id": self.organ_id, "organ_version": self.organ_version, "state": self.state,
                "answer": None if self.answer is None else dict(self.answer),
                "proof": dict(self.proof), "assumptions": list(self.assumptions),
                "uncertainty": self.uncertainty, "expenditure": self.expenditure.to_dict(),
                "dependencies": list(self.dependencies), "origin": self.origin,
                "notes": list(self.notes)}
