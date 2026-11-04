"""The executable IntelligenceGenome library, projected onto GREG's one cognition path.

Each module listed in ``MODULES`` exports ``INTELLIGENCES`` (a list of ``Executable``). This library:

* validates every genome and refuses duplicate ids, families or operations;
* projects each onto the existing family catalog (``greg/cognition/catalog.py``) as
  ``(layer, (operation,), (epistemic_class,), "genome_certificate", dependency)``, so the existing
  CapabilityRegistry, eligibility, isolated worker, independent verifier, receipt and competence
  settlement apply unchanged - there is no second registry, router or ledger;
* adapts ``solve`` to the worker's result shape and ``verify`` to the verifier's check table.

Modules are imported lazily by family, so a worker that runs one intelligence imports one module.
Registration in the catalog never attaches anything: non-seed families start VERIFIED (registered,
withheld) and only a founder CAPABILITY_ATTACH makes one usable on a body (``catalog.initial_state``).
"""
from __future__ import annotations

from functools import lru_cache
import importlib

from .contract import Executable, GenomeError

# module path -> layer it implements (documentation; each genome declares its own layer)
MODULES = (
    "greg.cognition.genomes.flow",          # L3 graph max-flow / min-cut; capacity expansion compiler
    "greg.cognition.genomes.forecasting",   # L3 time-series forecasting with calibrated quantiles
    "greg.cognition.genomes.decision",      # L3 decision analysis (preposterior / value of information)
    "greg.cognition.genomes.basal",         # L1 basal / primitive intelligences
    "greg.cognition.genomes.collective",    # L2 distributed / collective intelligences
    "greg.cognition.genomes.solvers_b",     # L3 further direct mathematical intelligences (batch B)
    "greg.cognition.genomes.solvers_c",     # L3 mechanism design, verification, control, causal (batch C)
    "greg.cognition.genomes.developmental",  # L4 developmental / target-state repair
)
PROOF_CLASS = "genome_certificate"
PROOF_FIELDS = ("intelligence_id", "version", "evidence_type", "inputs_digest", "certificate", "limits")


def _import(name: str):
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError as exc:
        if exc.name == name:          # a library module not yet built is absent, not an error
            return None
        raise


@lru_cache(maxsize=1)
def executables() -> dict[str, Executable]:
    """family -> Executable, validated, with ids, families and operations unique."""
    out, ids, ops = {}, set(), set()
    for name in MODULES:
        module = _import(name)
        if module is None:
            continue
        for item in getattr(module, "INTELLIGENCES", ()):
            g = item.genome.validate()
            if g.family in out or g.intelligence_id in ids or g.operation in ops:
                raise GenomeError(f"duplicate genome identity: {g.intelligence_id}")
            out[g.family] = item
            ids.add(g.intelligence_id)
            ops.add(g.operation)
    return out


def catalog_families() -> dict[str, tuple]:
    """The projection ``catalog.FAMILIES`` merges: family -> (layer, ops, classes, proof class, dependency)."""
    return {family: (x.genome.layer, (x.genome.operation,), (x.genome.epistemic_class,), PROOF_CLASS,
                     x.genome.dependency)
            for family, x in executables().items()}


def genome(family: str):
    return executables()[family].genome


def run(family: str, data: dict, geometry: dict) -> dict:
    """Worker adapter: an intelligence's ``solve`` -> the cognition worker's result shape."""
    from greg.cognition.contracts import digest
    item = executables()[family]
    g = item.genome
    budget = {"latency_s": float(geometry.get("latency_limit", 5.0)) * 0.8,
              "compute": int(geometry.get("compute_limit", 10000))}
    out = item.solve(data, budget)
    if not isinstance(out, dict) or set(out) != {"output", "certificate", "status", "missing"}:
        raise GenomeError(f"{family} returned an invalid solve result")
    proof = {"intelligence_id": g.intelligence_id, "version": g.version, "evidence_type": g.evidence_type,
             "inputs_digest": digest(data), "certificate": out["certificate"],
             "limits": list(g.known_failure_modes)}
    status = {"ANSWER": "ANSWER", "ABSTAIN": "ABSTAIN", "UNKNOWN": "UNKNOWN"}[out["status"]]
    return {"output": out["output"], "proof": proof, "status": status,
            "formal_validity": "VALID_CONDITIONAL_ON_MODEL" if g.evidence_type in (
                "exact_calculation", "optimality_certificate", "exhaustive_check") and status == "ANSWER"
            else "NOT_APPLICABLE",
            "missing_information": out["missing"], "empirical_validity": "WORLD_UNVERIFIED"}


def check(family: str, data: dict, output, proof: dict) -> dict:
    """Verifier adapter: the intelligence's independent check plus envelope bindings."""
    from greg.cognition.contracts import digest
    item = executables()[family]
    g = item.genome
    checks = {"genome_identity": proof.get("intelligence_id") == g.intelligence_id and proof.get("version") == g.version,
              "evidence_type_declared": proof.get("evidence_type") == g.evidence_type,
              "inputs_bound": proof.get("inputs_digest") == digest(data)}
    if output is not None:
        for name, ok in item.verify(data, output, proof.get("certificate") or {}).items():
            checks[f"independent:{name}"] = bool(ok)
    return checks
