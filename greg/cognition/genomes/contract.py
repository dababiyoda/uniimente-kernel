"""IntelligenceGenome contract: an intelligence is admitted by native competence, not by name.

Founder directive 2026-10-07 (INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION, sections 14-15, 25):
every intelligence family is an executable, inspectable genome with a native problem family, a simple
baseline, a strongest reasonable competitor, a held-out evaluation and an admission outcome. This module
is the contract only; executable intelligences live beside it and run on GREG's existing cognition path
(``greg.cognition.cortex.reason`` -> isolated worker -> independent verifier -> CognitiveReceipt). A genome
is a projection onto the existing CapabilityRegistry family catalog, never a second registry, and its
authority ceiling is read-only by construction.

An executable intelligence supplies:

    solve(data, budget)            -> {"output", "certificate", "status", "missing"}   (bounded, pure)
    verify(data, output, cert)     -> {check_name: bool}   an independent check, never the solver's code path
    instance(seed)                 -> (data, truth)        native benchmark generator; truth from an
                                                           independent method (exhaustive, analytic, long
                                                           reference run or real outcome)
    score(data, truth, output)     -> {"quality": float (higher is better), "category": correct|wrong|abstain}
    baseline(data), competitor(data) -> output in the same contract, or None to abstain
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import math
from typing import Any, Callable, Mapping

BUILDABILITY = ("BUILDABLE_NOW", "EXPERIMENTAL_NOW", "FRONTIER_RESEARCH", "SCIENCE_FICTION_DESCENDANT")
ADMISSION = ("DEFAULT_FOR_GEOMETRY", "NICHE_CAPABILITY", "COMPOSITION_ONLY", "EXPERIMENTAL", "SUPERSEDED",
             "REJECTED", "FRONTIER_HORIZON", "UNEVALUATED")
LAYERS = {1: "primitive_basal", 2: "distributed_collective", 3: "solver_macro_cognitive",
          4: "developmental_morphogenetic", 5: "meta_institutional"}
# Directive section 12: do not call every artifact "proof"; label its epistemic type.
EVIDENCE_TYPES = ("exact_calculation", "optimality_certificate", "feasibility_witness", "exhaustive_check",
                  "counterexample", "statistical_estimate", "posterior", "forecast_distribution", "simulation",
                  "control_trace", "heuristic_trace", "collective_trace", "developmental_trace",
                  "decision_analysis", "human_attestation")
CATEGORIES = ("correct", "wrong", "abstain")
EPISTEMIC_CLASSES = ("deductive", "arithmetic", "constraint_feasibility", "optimization", "estimate",
                     "prediction", "causal", "semantic", "strategic", "normative", "legal", "physical",
                     "institutional_acceptance")


class GenomeError(ValueError):
    pass


@dataclass(frozen=True)
class IntelligenceGenome:
    """Directive section 14, one attribute per field (plus operation/epistemic class for the catalog)."""

    intelligence_id: str
    version: str
    family: str                      # catalog family key -> capability id ``cognition.<family>``
    layer: int
    operation: str                   # the operation name on GREG's cognition path (unique)
    epistemic_class: str             # problem_geometry, in GREG's epistemic vocabulary
    subgeometry: str
    source_provenance: str
    buildability: str
    native_representation: str
    required_inputs: tuple[str, ...]
    output_contract: Mapping[str, str]
    algorithm_or_runtime: str
    parameters: Mapping[str, Any]
    memory_model: str
    learning_rule: str
    composition_inputs: tuple[str, ...]
    composition_outputs: tuple[str, ...]
    evidence_type: str
    verification_method: str
    confidence_semantics: str
    resource_profile: str
    latency_profile: str
    known_strengths: tuple[str, ...]
    known_failure_modes: tuple[str, ...]
    counterindications: tuple[str, ...]
    abstention_conditions: tuple[str, ...]
    benchmark_suite: str
    baseline: str
    competitor: str
    lineage: tuple[str, ...]
    rollback: str = "founder CAPABILITY_DETACH of cognition.<family>; receipts retained; no state to unwind"
    replacement_interface: str = "same operation, data and output contract on greg.cognition.cortex.reason"
    held_out_result: str = "UNEVALUATED"     # path of the frozen admission evidence, set by the harness
    authority_ceiling: str = "read_only"
    consequence_limit: str = "read_only"
    dependency: str | None = None             # an installable distribution name, or None (stdlib/numpy only)
    standalone_decision: bool = True          # False: produces an intermediate representation only

    def validate(self) -> "IntelligenceGenome":
        problems = []
        if not self.intelligence_id or "." not in self.intelligence_id:
            problems.append("intelligence_id is layer.name")
        if self.layer not in LAYERS:
            problems.append("layer 1-5")
        if not self.family.replace("_", "").replace(".", "").isalnum():
            problems.append("family is a catalog key")
        if self.buildability not in BUILDABILITY:
            problems.append(f"buildability {self.buildability!r}")
        if self.evidence_type not in EVIDENCE_TYPES:
            problems.append(f"evidence_type {self.evidence_type!r}")
        if self.epistemic_class not in EPISTEMIC_CLASSES:
            problems.append(f"epistemic_class {self.epistemic_class!r}")
        if self.authority_ceiling != "read_only" or self.consequence_limit != "read_only":
            problems.append("an intelligence cannot carry effect authority")
        for name in ("required_inputs", "known_strengths", "known_failure_modes", "counterindications",
                     "abstention_conditions", "lineage"):
            if not getattr(self, name):
                problems.append(f"{name} must be declared")
        if not self.baseline or not self.competitor or not self.benchmark_suite:
            problems.append("baseline, competitor and benchmark_suite are required for admission")
        if problems:
            raise GenomeError(f"{self.intelligence_id}: " + "; ".join(problems))
        return self

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Executable:
    genome: IntelligenceGenome
    solve: Callable[[dict, dict], dict]
    verify: Callable[[dict, dict, dict], dict]
    instance: Callable[[int], tuple]
    score: Callable[[dict, dict, Any], dict]
    baseline: Callable[[dict], Any]
    competitor: Callable[[dict], Any]
    subregion: Callable[[dict], str] | None = None     # native sub-regions for niche analysis
    tolerance: float = 1e-9                             # quality differences at or below this are ties
    notes: Mapping[str, str] = field(default_factory=dict)


def answer(output, certificate, *, status="ANSWER", missing=()) -> dict:
    """The return shape of ``solve``. status: ANSWER, ABSTAIN or UNKNOWN."""
    if status not in ("ANSWER", "ABSTAIN", "UNKNOWN"):
        raise GenomeError("solve status is ANSWER, ABSTAIN or UNKNOWN")
    if status == "ANSWER" and output is None:
        raise GenomeError("an ANSWER carries its output; abstain or report UNKNOWN instead")
    return {"output": output, "certificate": certificate, "status": status, "missing": list(missing)}


def finite(value, *, low=-1e12, high=1e12, name="value") -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise GenomeError(f"{name}: finite number in [{low}, {high}] required")
    return float(value)


def bounded_int(value, *, low=0, high=10_000, name="value") -> int:
    if type(value) is not int or not low <= value <= high:
        raise GenomeError(f"{name}: integer in [{low}, {high}] required")
    return value


def canonical_model(model):
    """A compiled integer model (the ``optimize`` family's format) in canonical form, or None if malformed.

    Returns ``(bounds, rows, objective)``: bounds ``{name: (low, high)}``; rows a Counter of
    ``(frozenset(nonzero coefficients), op, rhs, requirement_id)`` (row order carries no meaning);
    objective ``(frozenset(nonzero coefficients), sense)``. Verifiers compare it with the model the problem
    statement implies, derived on their own."""
    from collections import Counter
    if not isinstance(model, dict) or set(model) != {"variables", "constraints", "objective"}:
        return None
    variables, constraints, objective = model["variables"], model["constraints"], model["objective"]

    def num(v):
        return type(v) in (int, float) and math.isfinite(v)
    if not isinstance(variables, dict) or not all(
            isinstance(k, str) and isinstance(b, list) and len(b) == 2 and num(b[0]) and num(b[1]) and b[0] <= b[1]
            for k, b in variables.items()):
        return None

    def coefficients(c):
        if not isinstance(c, dict) or not all(k in variables and num(v) for k, v in c.items()):
            return None
        return frozenset((k, v) for k, v in c.items() if v != 0)
    if not isinstance(constraints, list):
        return None
    rows = Counter()
    for row in constraints:
        if (not isinstance(row, dict) or set(row) != {"coefficients", "op", "rhs", "requirement_id"}
                or row["op"] not in ("<=", ">=", "==") or not num(row["rhs"])
                or not isinstance(row["requirement_id"], str)):
            return None
        c = coefficients(row["coefficients"])
        if c is None:
            return None
        rows[(c, row["op"], row["rhs"], row["requirement_id"])] += 1
    if (not isinstance(objective, dict) or set(objective) != {"coefficients", "sense"}
            or objective["sense"] not in ("min", "max")):
        return None
    obj = coefficients(objective["coefficients"])
    if obj is None:
        return None
    return {k: (b[0], b[1]) for k, b in variables.items()}, rows, (obj, objective["sense"])


def model_optimum(model):
    """Evaluation side only (``score``; never ``solve`` or ``verify``): the exact optimum of a small compiled
    integer model by SciPy HiGHS branch-and-bound, or None when it is infeasible or unsolved."""
    import numpy as np
    from scipy.optimize import Bounds, LinearConstraint, milp
    names = sorted(model["variables"])
    index = {n: i for i, n in enumerate(names)}
    sign = -1.0 if model["objective"]["sense"] == "max" else 1.0
    c = np.zeros(len(names))
    for k, v in model["objective"]["coefficients"].items():
        c[index[k]] = sign * v
    rows, low, high = [], [], []
    for row in model["constraints"]:
        a = np.zeros(len(names))
        for k, v in row["coefficients"].items():
            a[index[k]] = v
        rows.append(a)
        low.append(row["rhs"] if row["op"] in (">=", "==") else -np.inf)
        high.append(row["rhs"] if row["op"] in ("<=", "==") else np.inf)
    res = milp(c, constraints=[LinearConstraint(np.array(rows), low, high)] if rows else (),
               bounds=Bounds([model["variables"][n][0] for n in names], [model["variables"][n][1] for n in names]),
               integrality=np.ones(len(names)))
    return float(sign * res.fun) if res.success else None
