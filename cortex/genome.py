"""IntelligenceGenome: a cognitive projection of the existing Capability Genome.

Build prompt item 1: reuse the Capability Genome's identifiers, versioning,
persistence, lifecycle and eligibility machinery. So an IntelligenceGenome is
*not* a second registry. It is a ``CapabilityGenome`` (registered in the one
``capabilities.genome.GenomeRegistry``, which ledgers the registration when a
ledger is attached) plus a ``CognitiveProfile`` keyed by the same
``name@version``. Eligibility first calls ``GenomeRegistry.may_instantiate``.

A profile never carries a competence score. ``benchmark_history`` holds only
references to result files; competence comes from settled outcomes in
``cortex.memory`` and can reorder eligible methods, never widen eligibility.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from capabilities.genome import (AuthorityEnvelope, CapabilityGenome, GenomeError,
                                 GenomeRegistry)

from .contracts import (CONSEQUENCE_CLASSES, EPISTEMIC_CLASSES, IMPLEMENTED_PROOF_CLASSES,
                        LAYERS, PROOF_CLASSES, ProblemGeometry, consequence_rank, digest)

# UNIIMENTE_FINAL_BUILD_ORDER §4.3 lifecycle statuses.
LIFECYCLE = ("DISCOVERED", "SPECIFIED", "WRAPPED", "TESTED", "SANDBOXED", "SHADOW", "CANARY",
             "ACTIVE", "SPECIALIZED", "FALLBACK", "SUPERSEDED", "HISTORICAL", "QUARANTINED")
# Statuses a router may execute. The seed experiment runs organs SANDBOXED:
# executable inside the experiment, attached to no runtime and no Gate.
ROUTABLE_LIFECYCLE = ("SANDBOXED", "SHADOW", "CANARY", "ACTIVE", "SPECIALIZED", "FALLBACK")
ROLES = ("solver", "verifier", "reserved")
# Build prompt item 2: a biological concept must compile to all of these.
BIO_FIELDS = ("mechanism", "state_variables", "interface", "feedback_loop",
              "measurable_behavior", "test", "failure_condition")


@dataclass(frozen=True)
class CognitiveProfile:
    """Build prompt item 4 field list, one attribute each."""

    role: str
    layer: str
    supported_geometries: tuple[str, ...]
    input_contract: Mapping[str, Any]
    output_contract: Mapping[str, Any]
    proof_classes: tuple[str, ...]
    observations: tuple[str, ...]
    state: str
    memory_scope: str
    update_rules: str
    recruitment: str
    inhibition: str
    evidence_requirements: tuple[str, ...]
    cost_usd_per_call: float
    latency_s_budget: float
    cognitive_light_cone: Mapping[str, Any]
    authority_ref: str
    contraindications: tuple[str, ...]
    abstention_conditions: tuple[str, ...]
    failure_modes: tuple[str, ...]
    lineage: tuple[str, ...]
    benchmark_history: tuple[str, ...]
    failure_diversity_key: str
    shared_dependencies: tuple[str, ...]
    lifecycle: str
    enabled: bool
    biological_concept: Mapping[str, Any] | None = None

    def validate(self) -> list[str]:
        problems: list[str] = []
        if self.role not in ROLES:
            problems.append(f"unknown role {self.role!r}")
        if self.layer not in LAYERS:
            problems.append(f"unknown layer {self.layer!r}")
        if not self.supported_geometries:
            problems.append("profile must declare supported geometries")
        for g in self.supported_geometries:
            if g not in EPISTEMIC_CLASSES:
                problems.append(f"unknown geometry {g!r}")
        for p in self.proof_classes:
            if p not in PROOF_CLASSES:
                problems.append(f"unknown proof class {p!r}")
        if self.lifecycle not in LIFECYCLE:
            problems.append(f"unknown lifecycle {self.lifecycle!r}")
        if self.enabled and self.lifecycle not in ROUTABLE_LIFECYCLE:
            problems.append(f"enabled profile must be routable, not {self.lifecycle}")
        if self.enabled and self.role == "reserved":
            problems.append("a reserved family may not be enabled in the seed experiment")
        if self.enabled and not set(self.proof_classes) <= set(IMPLEMENTED_PROOF_CLASSES):
            problems.append("an enabled profile may only emit implemented proof classes")
        if self.cost_usd_per_call < 0 or self.latency_s_budget <= 0:
            problems.append("cost must be >= 0 and latency budget > 0")
        cone = self.cognitive_light_cone
        if cone.get("modifies"):
            problems.append("a cognitive light cone may observe but never modify the world")
        if cone.get("max_informed_consequence") not in CONSEQUENCE_CLASSES:
            problems.append("light cone requires max_informed_consequence")
        if any(":" in ref and ref.split(":", 1)[0] == "score" for ref in self.benchmark_history):
            problems.append("benchmark_history holds result references, never self-asserted scores")
        for c in self.contraindications:
            if "=" not in c:
                problems.append(f"contraindication {c!r} must be field=value")
        if not self.failure_modes or not self.abstention_conditions:
            problems.append("profile must declare failure modes and abstention conditions")
        if not self.failure_diversity_key:
            problems.append("profile must declare a failure-diversity key")
        if self.biological_concept is not None:
            missing = [f for f in BIO_FIELDS if not self.biological_concept.get(f)]
            if missing:
                problems.append(f"biological concept must compile to a mechanism; missing {missing}")
        return problems

    def to_dict(self) -> dict:
        out = {k: (list(v) if isinstance(v, tuple) else v) for k, v in self.__dict__.items()}
        out["input_contract"] = dict(self.input_contract)
        out["output_contract"] = dict(self.output_contract)
        out["cognitive_light_cone"] = dict(self.cognitive_light_cone)
        out["biological_concept"] = None if self.biological_concept is None else dict(self.biological_concept)
        return out


@dataclass(frozen=True)
class IntelligenceGenome:
    capability: CapabilityGenome
    profile: CognitiveProfile

    @property
    def key(self) -> str:
        return f"{self.capability.name}@{self.capability.version}"

    def validate(self) -> list[str]:
        problems = list(self.capability.validate()) + self.profile.validate()
        if self.profile.authority_ref != self.key:
            problems.append("profile authority_ref must name the projected capability genome")
        # Cognition executes read-only. Its own execution envelope never
        # exceeds read_only; what it may *inform* is the light cone's business.
        if self.capability.authority.max_consequence_class != "read_only":
            problems.append("a cognitive organ's execution envelope must be read_only")
        return problems

    def to_dict(self) -> dict:
        cap = self.capability
        return {
            "key": self.key,
            "capability": {
                "name": cap.name, "version": cap.version, "description": cap.description,
                "interface": cap.interface, "contracts": list(cap.contracts),
                "authority": {"max_consequence_class": cap.authority.max_consequence_class,
                              "budget_ceiling_usd": cap.authority.budget_ceiling_usd,
                              "requires_human": cap.authority.requires_human},
                "acceptance_tests": list(cap.acceptance_tests),
                "failure_modes": list(cap.failure_modes),
                "recovery_path": cap.recovery_path, "legal_operator": cap.legal_operator,
            },
            "profile": self.profile.to_dict(),
        }


@dataclass(frozen=True)
class EligibilityResult:
    key: str
    eligible: bool
    may_recommend: bool
    reasons: tuple[str, ...]

    def to_dict(self) -> dict:
        return {"key": self.key, "eligible": self.eligible, "may_recommend": self.may_recommend,
                "reasons": list(self.reasons)}


class IntelligenceRegistry:
    """The cognitive view of the one Kernel genome registry."""

    def __init__(self, genomes: GenomeRegistry | None = None):
        self.genomes = genomes if genomes is not None else GenomeRegistry()
        self._profiles: dict[str, CognitiveProfile] = {}

    def register(self, genome: IntelligenceGenome) -> IntelligenceGenome:
        problems = genome.validate()
        if problems:
            raise GenomeError(f"invalid intelligence genome {genome.key}: {problems}")
        self.genomes.register(genome.capability)  # existing validation + ledger event
        self._profiles[genome.key] = genome.profile
        ledger = getattr(self.genomes, "ledger", None)
        if ledger is not None:
            ledger.append("event", {"type": "cortex.profile_registered", "genome": genome.key,
                                    "profile_digest": digest(genome.profile.to_dict())})
        return genome

    def get(self, key: str) -> IntelligenceGenome | None:
        name, _, version = key.partition("@")
        cap = self.genomes.get(name, version)
        profile = self._profiles.get(key)
        return None if cap is None or profile is None else IntelligenceGenome(cap, profile)

    def keys(self) -> list[str]:
        return sorted(self._profiles)

    def profiles(self) -> dict[str, CognitiveProfile]:
        return dict(self._profiles)

    def eligibility(self, geometry: ProblemGeometry, *, role: str = "solver") -> list[EligibilityResult]:
        """Deterministic, inspectable eligibility. Hard filters only; no ranking."""
        results = []
        for key in self.keys():
            profile = self._profiles[key]
            if profile.role != role:
                continue
            reasons: list[str] = []
            name, _, version = key.partition("@")
            if not profile.enabled:
                reasons.append(f"disabled family ({profile.lifecycle})")
            elif profile.lifecycle not in ROUTABLE_LIFECYCLE:
                reasons.append(f"lifecycle {profile.lifecycle} is not routable")
            if geometry.epistemic_class is None:
                reasons.append("epistemic class unresolved")
            elif geometry.epistemic_class not in profile.supported_geometries:
                reasons.append(f"does not support {geometry.epistemic_class}")
            ok, why = self.genomes.may_instantiate(name, version, requested_class="read_only",
                                                   requested_budget_usd=profile.cost_usd_per_call)
            if not ok:
                reasons.append(why)
            geo = geometry.to_dict()
            for contraindication in profile.contraindications:
                field_name, _, value = contraindication.partition("=")
                if str(geo.get(field_name)) == value:
                    reasons.append(f"contraindicated: {contraindication}")
            ceiling = profile.cognitive_light_cone["max_informed_consequence"]
            may_recommend = consequence_rank(geometry.consequence_class) <= consequence_rank(ceiling)
            eligible = not reasons
            if eligible and not may_recommend:
                reasons.append(f"{geometry.consequence_class} exceeds light-cone ceiling {ceiling}: assist then hand off")
            results.append(EligibilityResult(key, eligible, eligible and may_recommend, tuple(reasons)))
        return results


# ------------------------------------------------------------------ seed + reserved families
def _capability(name: str, description: str, inputs: dict, outputs: dict,
                acceptance: list[str], failures: list[str], version: str = "0.1.0") -> CapabilityGenome:
    return CapabilityGenome(
        name=name, version=version, description=description,
        interface={"inputs": inputs, "outputs": outputs},
        contracts=["cortex-problem-geometry", "cortex-proof-artifact", "cortex-receipt"],
        authority=AuthorityEnvelope(max_consequence_class="read_only", budget_ceiling_usd=0.0,
                                    requires_human=False),
        acceptance_tests=acceptance, failure_modes=failures,
        recovery_path="unregister the profile; routes fall back to abstain or handoff",
    )


def _profile(key: str, *, role: str, layer: str, geometries: tuple, proofs: tuple, observations: tuple,
             state: str, update: str, recruitment: str, inhibition: str, evidence: tuple,
             ceiling: str, diversity: str, deps: tuple, lifecycle: str, enabled: bool,
             contraindications: tuple = (), abstain: tuple = ("required input absent",),
             failures: tuple = ("mechanism unavailable",), lineage: tuple = (),
             bio: Mapping[str, Any] | None = None, cost: float = 0.0, latency: float = 30.0,
             inputs: Mapping | None = None, outputs: Mapping | None = None,
             benchmarks: tuple = ()) -> CognitiveProfile:
    return CognitiveProfile(
        role=role, layer=layer, supported_geometries=geometries,
        input_contract=inputs or {"problem": "cortex-problem-geometry"},
        output_contract=outputs or {"result": "cortex-proof-artifact"},
        proof_classes=proofs, observations=observations, state=state,
        memory_scope="per-problem; no cross-problem memory in v0.1", update_rules=update,
        recruitment=recruitment, inhibition=inhibition, evidence_requirements=evidence,
        cost_usd_per_call=cost, latency_s_budget=latency,
        cognitive_light_cone={"observes": list(observations), "modifies": [],
                              "max_informed_consequence": ceiling, "horizon": "single problem"},
        authority_ref=key, contraindications=contraindications, abstention_conditions=abstain,
        failure_modes=failures, lineage=lineage, benchmark_history=tuple(benchmarks),
        failure_diversity_key=diversity, shared_dependencies=deps, lifecycle=lifecycle,
        enabled=enabled, biological_concept=bio,
    )


SEED_ORGANS = {
    "cortex.semantic": dict(
        description="Source-grounded synthesis through the existing local model integration.",
        role="solver", layer="solver_macro_cognitive",
        geometries=("semantic", "strategic"), proofs=("semantic_sourced",),
        observations=("question", "supplied sources"),
        state="stateless per call", update="none in v0.1; competence only via cortex.memory",
        recruitment="recruited for semantic geometry with supplied sources",
        inhibition="inhibited when no sources are supplied or the model is unreachable",
        evidence=("at least one supplied source",), ceiling="internal_write", diversity="llm",
        deps=("model:local-openai-protocol", "egregore.local_model"), lifecycle="SANDBOXED",
        enabled=True, abstain=("no sources", "model unavailable", "no claim survives source check"),
        failures=("hallucinated quote", "prompt injection in sources", "model outage"),
        lineage=("egregore/local_model.py", "docs/OPEN_SOURCE_STACK.md"),
        acceptance=["every returned claim quotes an exact span of a cited source"],
        benchmarks=("tests/evidence/cortex-seed-v0.1/heldout-results.json#routed_seed",)),
    "cortex.estimation.fermi": dict(
        description="Explicit decomposition with units, ranges, dependencies, sensitivity.",
        role="solver", layer="solver_macro_cognitive", geometries=("estimate",),
        proofs=("estimation",), observations=("decomposition", "input ranges", "correlations"),
        state="seeded Monte Carlo sample", update="none", recruitment="recruited for estimate geometry",
        inhibition="inhibited by dimensional mismatch or non-positive-definite dependencies",
        evidence=("ranges for every input",), ceiling="external_contact",
        diversity="monte_carlo_decomposition", deps=("python-stdlib",), lifecycle="SANDBOXED",
        enabled=True, abstain=("dimension mismatch", "malformed dependency matrix"),
        failures=("anchored ranges", "missing driver", "wrong independence assumption"),
        acceptance=["result unit equals the declared target unit"],
        benchmarks=("tests/evidence/cortex-seed-v0.1/heldout-results.json#routed_seed",)),
    "cortex.formal.z3": dict(
        # 0.1.1: an exhausted Z3 timeout ("canceled") is TIMEOUT, and an undecided witness
        # check stops the run instead of counting as agreement. 0.2.0: optimization with an
        # optimality certificate. Earlier versions are preserved in history.
        version="0.2.0",
        description="Formal feasibility, entailment and certified optimization on an inspectable model via Z3.",
        role="solver", layer="solver_macro_cognitive",
        geometries=("deductive_logical", "constraint_feasibility", "optimization", "arithmetic"), proofs=("formal",),
        observations=("structured model", "obligations", "witnesses", "premises"),
        state="solver session per problem", update="none",
        recruitment="recruited only when a structured model exists",
        inhibition="inhibited when the encoding fails discrepancy or witness checks",
        evidence=("structured model", "enumerated obligations"), ceiling="external_contact",
        diversity="smt", deps=("solver:z3",), lifecycle="SANDBOXED", enabled=True,
        abstain=("formalization incomplete", "solver unavailable", "timeout"),
        failures=("unfaithful encoding", "unverified premises", "solver outage"),
        acceptance=["SAT/UNSAT agrees with requester witnesses; UNSAT carries a core"],
        benchmarks=("tests/evidence/cortex-seed-v0.1/heldout-results.json#routed_seed",)),
    "cortex.evidence_causal": dict(
        description="Evidence assessment and gated causal estimation.",
        role="solver", layer="solver_macro_cognitive",
        geometries=("semantic", "prediction", "causal", "physical_perceptual"),
        proofs=("evidence_assessment", "causal_estimate"),
        observations=("evidence records", "provenance", "freshness", "causal spec", "data"),
        state="stateless", update="none",
        recruitment="recruited for empirical claims with evidence records or a causal spec",
        inhibition="inhibited when identification requirements are absent",
        evidence=("evidence records with provenance",), ceiling="external_contact",
        diversity="evidence_rules_and_adjustment", deps=("python-stdlib",), lifecycle="SANDBOXED",
        enabled=True, abstain=("not identified", "insufficient evidence", "contested"),
        failures=("unmeasured confounding", "stale evidence", "model output as evidence"),
        acceptance=["no causal estimate without estimand, assumptions, data, adjustment, method"],
        benchmarks=("tests/evidence/cortex-seed-v0.1/heldout-results.json#routed_seed",)),
    "cortex.deterrence.accountability": dict(
        # Added in cortex 0.1.5 for the founder's "maximize ... deterrence" (review pass 2, B36).
        description="Lawful deterrence assessment: Becker expected-value condition over declared ranges; "
                    "coercive interventions refused; external actions handed off.",
        role="solver", layer="solver_macro_cognitive", geometries=("strategic",),
        proofs=("deterrence_assessment",),
        observations=("declared parameter ranges", "lawful intervention effects", "costs", "harm vectors"),
        state="seeded sampler per problem", update="none",
        recruitment="recruited only when a structured deterrence model exists",
        inhibition="coercive or rights-violating interventions are refused before ranking",
        evidence=("declared ranges with sources",), ceiling="internal_write",
        diversity="expected_value_incentive_model", deps=("python-stdlib",), lifecycle="SANDBOXED",
        enabled=True, abstain=("no deterrence model", "malformed parameters"),
        failures=("risk-neutrality assumption", "displacement to other misconduct", "severity over-weighted"),
        acceptance=["no coercive or rights-violating intervention is ever ranked",
                    "interventions reaching another party are handed off"]),
    "cortex.verifier.adversarial": dict(
        description="Rule-based adversarial verification of artifacts and evidence.",
        role="verifier", layer="meta_polyintelligence_cortex", geometries=EPISTEMIC_CLASSES,
        proofs=("verifier_findings",), observations=("artifact", "evidence", "geometry", "disposition"),
        state="stateless", update="none", recruitment="runs on every routed result",
        inhibition="never inhibited; findings may only lower a disposition",
        evidence=("the artifact under attack",), ceiling="external_contact",
        diversity="rule_based_attack", deps=("python-stdlib",), lifecycle="SANDBOXED", enabled=True,
        abstain=("artifact missing",), failures=("rule blind spot",),
        acceptance=["a critical finding always blocks recommend"],
        benchmarks=("tests/evidence/cortex-seed-v0.1/heldout-results.json#routed_seed",)),
}

_BIO = lambda mech, state, iface, loop, measure, test, fail: {  # noqa: E731
    "mechanism": mech, "state_variables": state, "interface": iface, "feedback_loop": loop,
    "measurable_behavior": measure, "test": test, "failure_condition": fail}

# Build prompt item 5: future families are represented by compatible profiles,
# registered and disabled. None executes in the seed. Biological inspirations
# are compiled to mechanisms (item 2) so they cannot remain vocabulary.
RESERVED_FAMILIES = {
    "cortex.optimization.cpsat": ("solver_macro_cognitive", ("optimization", "constraint_feasibility"), "optimization", "cp_sat", None),
    "cortex.graph.search": ("solver_macro_cognitive", ("optimization", "strategic"), "optimization", "graph_search", None),
    "cortex.probabilistic.bayes": ("solver_macro_cognitive", ("prediction", "estimate"), "bayesian", "probabilistic_programming", None),
    "cortex.control.feedback": ("primitive_basal", ("physical_perceptual",), "simulation", "feedback_control", None),
    "cortex.sequential.bandit": ("solver_macro_cognitive", ("prediction", "strategic"), "bayesian", "sequential_decision", None),
    "cortex.pattern.anomaly": ("primitive_basal", ("physical_perceptual", "prediction"), "measurement", "statistical_pattern", None),
    "cortex.information.voi": ("meta_polyintelligence_cortex", ("strategic", "estimate"), "estimation", "value_of_information", None),
    "cortex.simulation.twin": ("solver_macro_cognitive", ("strategic", "causal"), "simulation", "simulation", None),
    "cortex.game.mechanism": ("solver_macro_cognitive", ("strategic",), "simulation", "game_theory", None),
    "cortex.human.panel": ("distributed_collective", ("normative_value", "legal", "institutional_acceptance"), "human_adjudication", "human_judgment", None),
    # Added in cortex 0.1.4 from review pass 2 (B06, B13, B28, B30): families the review named
    # that had no extension point.
    "cortex.exact.symbolic": ("solver_macro_cognitive", ("arithmetic",), "formal", "exact_symbolic", None),
    "cortex.search.heuristic": ("solver_macro_cognitive", ("strategic", "optimization"), "optimization", "heuristic_search", None),
    "cortex.meta.mental_models": ("meta_polyintelligence_cortex", ("strategic",), "estimation", "representation_operators", None),
    "cortex.meta.metaconsensus": ("meta_polyintelligence_cortex", ("strategic", "causal", "prediction"), "simulation", "epistemic_jurisdiction", None),
    "cortex.collective.hive_quorum": ("distributed_collective", ("strategic",), "simulation", "quorum",
        _BIO("independent scouts accumulate noisy evidence; cross-inhibition; quorum threshold",
             "per-option support counts, inhibition rate, quorum threshold", "candidate options in, chosen option out",
             "support recruits more evaluation; cross-inhibition suppresses rivals", "decision accuracy and time vs Bayesian model selection",
             "beat Bayesian model selection on a frozen option suite", "deadlock or premature quorum on equal options")),
    "cortex.collective.stigmergy": ("distributed_collective", ("optimization",), "optimization", "ant_colony",
        _BIO("agents deposit evaporating traces on paths; successful paths reinforced", "trace strength per edge, evaporation rate",
             "graph in, path out", "trace -> path choice -> reinforcement -> evaporation", "path cost vs Dijkstra/CP-SAT",
             "match or beat exact solvers on a frozen routing suite", "stagnation on a suboptimal path")),
    "cortex.collective.swarm_pso": ("distributed_collective", ("optimization",), "optimization", "particle_swarm",
        _BIO("particles move by inertia, personal best and neighborhood best", "positions, velocities, bests",
             "objective in, optimum out", "best positions attract particles", "objective value vs gradient/CMA baselines",
             "beat baselines on continuous benchmark suite", "premature convergence")),
    "cortex.collective.slime_network": ("distributed_collective", ("optimization",), "optimization", "adaptive_network",
        _BIO("tube conductance grows with flux and decays without it", "conductance per edge, flux", "terminals in, network out",
             "flux reinforces conductance; unused edges prune", "cost/efficiency/fault-tolerance vs Steiner heuristics",
             "compare on frozen network-design suite", "fragile tree lacking redundancy")),
    "cortex.collective.immune": ("distributed_collective", ("physical_perceptual", "prediction"), "measurement", "anomaly_tolerance",
        _BIO("anomaly -> challenge -> verification -> quarantine -> revoke -> repair -> recouple, with tolerance", "self set, anomaly scores, quarantine list",
             "event stream in, quarantine proposals out", "verified incidents update tolerance thresholds", "detection rate vs false-positive (autoimmunity) rate",
             "replay incident corpus with known benign novelty", "autoimmune quarantine of legitimate novelty")),
    "cortex.collective.ecology_market": ("distributed_collective", ("strategic",), "simulation", "allocation_market",
        _BIO("methods bid expected accuracy, cost, latency; outcomes settle reputation; diversity protected", "bids, settled reputation, niche occupancy",
             "problem in, allocation out", "settled outcomes change future bids and niches", "routing regret vs static policy",
             "held-out regret after settlement", "monoculture or gamed bids")),
    "cortex.developmental.evolutionary": ("developmental_morphogenetic", ("optimization",), "optimization", "evolutionary_search",
        _BIO("population -> mutation -> recombination -> evaluation -> selection -> lineage", "population, fitness, lineage",
             "machine-evaluable spec in, candidate program out", "selection pressure from an independent evaluator", "held-out improvement per generation",
             "several generations improve held-out score without evaluator gaming", "evaluator gaming")),
    "cortex.developmental.program_synthesis": ("developmental_morphogenetic", ("deductive_logical", "optimization"), "formal", "program_synthesis", None),
    "cortex.developmental.constraint_release": ("developmental_morphogenetic", ("strategic",), "simulation", "constraint_release",
        _BIO("capabilities removed from habitual topology recombine under altered rules in a sandbox", "topology, rule set, outcomes",
             "capability set in, candidate topology out", "useful novel topologies retained", "novel topology beats library baseline",
             "discover a topology absent from the candidate library that beats baseline", "novelty without usefulness")),
    "cortex.developmental.morphogenetic": ("developmental_morphogenetic", ("strategic",), "simulation", "functional_morphogenesis",
        _BIO("target function preserved while internal organization changes after unseen damage", "target function, capability topology, deficit field",
             "damage event in, restored structure out", "deficit recruits candidate capabilities until function returns", "unscripted functional recovery rate",
             "MICA/CDPE beats strong centralized adaptive baseline on unseen failures", "scripted repair masquerading as morphogenesis")),
    "cortex.developmental.molecular_micro": ("primitive_basal", ("prediction",), "measurement", "associative_microcircuit",
        _BIO("tiny networks form associative state from paired stimuli", "edge weights, activation, decay", "signals in, reflex out",
             "paired stimuli strengthen association; decay forgets", "precursor-detection accuracy per unit compute vs small classifier",
             "match small classifier at <1% compute", "spurious association")),
    "cortex.developmental.mica_field": ("developmental_morphogenetic", ("strategic",), "simulation", "local_field_coordination",
        _BIO("local cells exchange bounded signals to regulate toward a target state", "cell states, field values", "local signals",
             "field gradients drive local correction", "recovery vs centralized controller", "developmental/ benchmark TARGET_FORM_001", "no advantage over centralized control")),
    "cortex.meta.global_workspace": ("meta_polyintelligence_cortex", ("strategic",), "simulation", "global_workspace",
        _BIO("competing modules; inhibition; selective broadcast; shared working memory", "module activations, workspace contents",
             "module outputs in, broadcast out", "broadcast content biases module competition", "decision quality vs plain orchestration",
             "beat simple orchestration on frozen mixed suite", "becomes a second Kernel or authority path")),
    "cortex.meta.active_inference": ("meta_polyintelligence_cortex", ("strategic", "prediction"), "bayesian", "active_inference",
        _BIO("generative model with hidden states, observations, transitions, policies, preferences, posterior beliefs",
             "beliefs over hidden states, preferences, policy posteriors", "observations in, policy out",
             "expected-free-energy-like policy selection updates beliefs", "task reward vs PID/bandit/MPC baselines",
             "beat simpler control on the target geometry", "claims active inference without a real generative model")),
}


def seed_registry(genomes: GenomeRegistry | None = None, *, include_reserved: bool = True) -> IntelligenceRegistry:
    """Register the five seed organs (SANDBOXED) and, optionally, the reserved families (disabled)."""
    registry = IntelligenceRegistry(genomes)
    for name, spec in SEED_ORGANS.items():
        spec = dict(spec)
        version = spec.pop("version", "0.1.0")
        cap = _capability(name, spec.pop("description"), {"problem": "cortex problem"},
                          {"result": "typed proof artifact"}, spec.pop("acceptance"),
                          list(spec["failures"]), version)
        profile = _profile(f"{name}@{version}", **spec)
        registry.register(IntelligenceGenome(cap, profile))
    if include_reserved:
        for name, (layer, geometries, proof, diversity, bio) in RESERVED_FAMILIES.items():
            cap = _capability(name, f"Reserved family {diversity}; no executor in the seed experiment.",
                              {"problem": "cortex problem"}, {"result": "typed proof artifact"},
                              [f"must beat the simpler baseline on its native geometry ({diversity})"],
                              ["not implemented"])
            profile = _profile(f"{name}@0.1.0", role="reserved", layer=layer, geometries=geometries,
                               proofs=(proof,), observations=("reserved",), state="none",
                               update="none", recruitment="never in v0.1", inhibition="disabled",
                               evidence=("reserved",), ceiling="read_only", diversity=diversity,
                               deps=(), lifecycle="SPECIFIED", enabled=False,
                               abstain=("disabled family",), failures=("not implemented",), bio=bio)
            registry.register(IntelligenceGenome(cap, profile))
    return registry
