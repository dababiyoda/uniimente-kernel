"""Cognitive extension of the existing CapabilityGenome and GenomeRegistry."""
from dataclasses import asdict, dataclass

from capabilities.genome import AuthorityEnvelope, CapabilityGenome, GenomeError
from egregore.contracts import canonical_copy
from .contracts import LAYERS


@dataclass(frozen=True)
class CognitiveProfile:
    layer: str
    geometries: tuple[str, ...]
    proof_classes: tuple[str, ...]
    enabled: bool
    observations: str = "supplied structured inputs and referenced ledger evidence only"
    state: str = "request-local; durable receipts owned by EvidenceLedger"
    memory_scope: str = "referenced evidence and geometry-specific outcome history"
    update_rule: str = "verified-outcome proposal; no automatic promotion"
    recruitment: str = "deterministic native-geometry match after eligibility"
    inhibition: str = "failed/unknown gates, invalid inputs, budget or verification failure"
    resource_model: str = "declared call, dollar and latency ceilings"
    cognitive_light_cone: str = "internal analysis; no external actions or authority creation"
    abstention_conditions: tuple[str, ...] = ("missing evidence", "unsupported geometry", "resource exhaustion")
    benchmark: str = "examples/cognition/seed-suite.json; synthetic functionality only"

    def to_dict(self):
        return canonical_copy(asdict(self))


@dataclass
class IntelligenceGenome(CapabilityGenome):
    cognitive_profile: CognitiveProfile | None = None

    def validate(self):
        problems = super().validate()
        p = self.cognitive_profile
        if not isinstance(p, CognitiveProfile):
            problems.append("cognitive profile required")
        elif p.layer not in LAYERS or not p.geometries or not p.proof_classes:
            problems.append("invalid cognitive profile")
        elif type(p.enabled) is not bool:
            problems.append("enabled must be boolean")
        if self.authority.max_consequence_class != "read_only" or self.authority.budget_ceiling_usd != 0:
            problems.append("seed genomes may only describe zero-dollar proposal-only analysis")
        return problems


SEED_METHODS = {
    "semantic": (("semantic",), ("semantic",)),
    "fermi": (("estimate",), ("fermi",)),
    "formal": (("formal",), ("formal",)),
    "evidence": (("factual", "causal", "legal", "normative"), ("evidence",)),
}
# Descriptive phenotypes in the same registry; no implementations are activated.
RESERVED_FAMILIES = {
    "primitive_control": "primitive_basal", "associative_microcircuits": "primitive_basal",
    "quorum": "distributed_collective", "stigmergy": "distributed_collective",
    "swarm": "distributed_collective", "ecological_allocation": "distributed_collective",
    "human_collective": "distributed_collective", "exact_symbolic": "solver_macro_cognitive",
    "optimization": "solver_macro_cognitive", "graph_search": "solver_macro_cognitive",
    "bayesian": "solver_macro_cognitive", "causal_estimation": "solver_macro_cognitive",
    "simulation": "solver_macro_cognitive", "control": "solver_macro_cognitive",
    "sequential_decision": "solver_macro_cognitive", "game_mechanism": "solver_macro_cognitive",
    "evolutionary_synthesis": "developmental_morphogenetic",
    "constraint_release": "developmental_morphogenetic",
    "functional_morphogenesis": "developmental_morphogenetic",
    "value_of_information": "meta_intelligence", "learned_portfolio": "meta_intelligence",
}
FUTURE_GEOMETRIES = {
    "primitive_control": ("control", "physical"), "associative_microcircuits": ("physical",),
    "quorum": ("strategic",), "stigmergy": ("search",), "swarm": ("optimization", "physical"),
    "ecological_allocation": ("optimization",), "human_collective": ("normative", "legal", "strategic"),
    "exact_symbolic": ("arithmetic",), "optimization": ("optimization",),
    "graph_search": ("search",), "bayesian": ("probabilistic", "prediction"),
    "causal_estimation": ("causal",), "simulation": ("strategic", "prediction"),
    "control": ("control",), "sequential_decision": ("control", "strategic"),
    "game_mechanism": ("strategic",), "evolutionary_synthesis": ("search", "optimization"),
    "constraint_release": ("search",), "functional_morphogenesis": ("control",),
    "value_of_information": ("probabilistic", "strategic"), "learned_portfolio": ("strategic",),
}


def register_seed_genomes(registry):
    for method in (*SEED_METHODS, *RESERVED_FAMILIES):
        active = method in SEED_METHODS
        if active:
            geometries, proofs = SEED_METHODS[method]
        else:
            geometries, proofs = FUTURE_GEOMETRIES[method], ("unimplemented",)
        profile = CognitiveProfile(
            layer=RESERVED_FAMILIES.get(method, "solver_macro_cognitive"),
            geometries=geometries, proof_classes=proofs, enabled=active)
        genome = IntelligenceGenome(
            name=f"cognition.{method}", version="0.1.0",
            description=f"{'Seed experiment' if active else 'Disabled future phenotype'}: {method}",
            interface={"inputs": {"request": "CognitiveRequest"}, "outputs": {"result": "CognitiveResult"}},
            contracts=["evidence", "outcome"], authority=AuthorityEnvelope("read_only", 0.0),
            acceptance_tests=["tests/unit/test_cognition_runtime.py"],
            failure_modes=["model/world mismatch", "missing evidence", "budget exhaustion"],
            recovery_path="detach proposer; retain receipts; restore previous routing configuration",
            cognitive_profile=profile)
        existing = registry.get(genome.name, genome.version)
        if existing is None:
            registry.register(genome)
        elif not isinstance(existing, IntelligenceGenome) or asdict(existing) != asdict(genome):
            raise GenomeError("seed genome version conflict; register a new version instead")
    return registry
