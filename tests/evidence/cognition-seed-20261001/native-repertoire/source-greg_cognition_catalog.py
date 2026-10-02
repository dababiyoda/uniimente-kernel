"""Cognitive metadata extends CapabilityGenome; entries alone are never completion."""
from dataclasses import asdict

from .contracts import CognitiveCapabilityProfile


# family -> (layer, operations, epistemic classes, proof class, dependency)
FAMILIES = {
    "evidence": (3, ("bind_evidence",), ("semantic",), "evidence_binding", None),
    "micro": (1, ("setpoint",), ("physical",), "pattern_evidence", None),
    "exact": (3, ("calculate", "polynomial"), ("arithmetic",), "exact_calculation", "sympy"),
    "estimation": (3, ("estimate",), ("estimate",), "bounded_estimate", None),
    "formal": (3, ("constraints",), ("deductive", "constraint_feasibility"), "formal_model", "z3-solver"),
    "optimization": (3, ("optimize",), ("optimization",), "optimization_certificate", "ortools"),
    "graph": (3, ("shortest_path",), ("optimization",), "search_trace", None),
    "search": (3, ("state_search",), ("optimization",), "search_trace", None),
    "flow": (3, ("max_flow",), ("optimization",), "flow_certificate", None),
    "linear": (3, ("linear_program",), ("optimization",), "linear_program_certificate", "ortools"),
    "probabilistic": (3, ("beta_update",), ("prediction",), "posterior", None),
    "causal": (3, ("treatment_effect",), ("causal",), "causal_identification", None),
    "control": (3, ("pid",), ("physical",), "control_trace", None),
    "information": (3, ("value_of_information",), ("strategic",), "information_value", None),
    "simulation": (3, ("simulate",), ("prediction",), "simulation_trace", None),
    "game": (3, ("minimax",), ("strategic",), "game_model", "scipy"),
    "protection": (3, ("protection_review", "deterrence_model"), ("strategic",), "game_model", None),
    "pattern": (3, ("anomalies",), ("prediction",), "pattern_evidence", None),
    "sequential": (3, ("mdp",), ("strategic",), "search_trace", None),
    "semantic": (3, ("interpret",), ("semantic", "strategic"), "sourced_claims", None),
    "human": (4, ("human_review",), ("normative", "legal", "institutional_acceptance"), "human_judgment", None),
    "collective": (4, ("quorum",), ("prediction",), "collective_trace", None),
    "evolutionary": (4, ("evolve_vector",), ("optimization",), "collective_trace", "scipy"),
}

# Existing alternative implementations retain their code and lineage. Cataloguing
# never silently activates the P5+ repertoire on a new body.
SEED_FAMILIES = frozenset(("micro", "exact", "estimation", "formal", "optimization", "causal", "evidence", "semantic"))
NATIVE_EXTENSION_FAMILIES = frozenset(("exact", "graph", "search", "flow", "linear", "probabilistic", "control", "information", "simulation", "game", "pattern", "sequential", "collective", "evolutionary", "human"))
NATIVE_LIMITS = {
    "probabilistic": "Beta-Bernoulli conjugate update only; no calibrated predictive claim",
    "control": "one clamped PID proposal; no plant stability qualification or actuation",
    "information": "declared finite decision-value scenarios; no empirical utility/probability identification",
    "simulation": "seeded iid Bernoulli-step simulator; no real-world calibration",
    "game": "bounded finite two-player zero-sum minimax with numerical primal/dual checks",
    "pattern": "population z-scores only; no out-of-sample detector qualification",
    "sequential": "fully observed finite-horizon supplied MDP; no open-world learned policy",
    "collective": "weighted quorum under declared group labels; actual independence unverified",
    "evolutionary": "seeded bounded quadratic vector search; analytic baseline stronger; no new algorithms",
    "human": "bounded proposed work/panel record; authentic professional judgment still required",
}

def initial_state(capability_id):
    if capability_id == "foundry.query":
        return "VERIFIED"
    family = capability_id.removeprefix("cognition.")
    return "VERIFIED" if capability_id.startswith("cognition.") and family in FAMILIES and family not in SEED_FAMILIES else "ATTACHED"


def profile(family):
    layer, operations, classes, proof, _ = FAMILIES[family]
    native = family in ("graph", "search", "flow", "linear")
    return CognitiveCapabilityProfile(family=family, layer=layer, operations=operations,
                                     epistemic_classes=classes, proof_class=proof,
                                     deterministic=family not in ("semantic",),
                                     latency_estimate_seconds=1.0 if family in ("formal", "optimization", "linear", "game", "evolutionary", "semantic") else .1,
                                     lineage=("INTENT-20260930-polyintelligence", "PR143/7105a7cbd013edd6bce88b9500e2b4477635c912") if native else ("INTENT-20260930-polyintelligence",),
                                     implementation_ref="greg/cognition/linear.py" if family == "linear" else "greg/cognition/network.py" if native else "greg/cognition/solvers.py",
                                     competence_limits=NATIVE_LIMITS.get(family, "bounded declarative native workload only; not general field mastery"),
                                     falsification_tests=("tests/unit/test_cognition_native_repertoire.py", "tests/integration/test_cognition_native_repertoire_mission.py") if family in NATIVE_LIMITS else ("tests/unit/test_greg_cognition.py",))


def builtin_entries(manifest_type, lazy):
    entries = {}
    for family in (*FAMILIES, "solve", "compose", "knowledge"):
        computational = family not in ("knowledge",)
        entries["cognition." + family] = (manifest_type(
            capability_id="cognition." + family, version="0.3.0" if family in NATIVE_EXTENSION_FAMILIES else "0.2.0", provider="greg-builtin",
            function="cognition." + family, description="Bounded " + family + " cognition with typed evidence and abstention",
            route="internal", consequence_class="read_only", target_prefix="cognition:",
            inputs={"problem_id": "str", "operation": "str", "data": "bounded dict"} if computational else {"none": "no parameters"},
            outputs={"receipt": "CognitiveReceipt", "authority_created": "false"} if computational else {"competence": "list"},
            retry_safe=True, strengthens=("eligibility", "routing", "proof", "settlement"),
            tests=("tests/unit/test_greg_cognition.py", "tests/integration/test_greg_cognition_mission.py"),
            provenance={"source": "uniimente-kernel/greg/cognition", "intent": "INTENT-20260930-polyintelligence"},
            network="egress-allowlist" if family in ("semantic", "solve", "compose") else "none",
            egress_allowlist=("127.0.0.1",) if family in ("semantic", "solve", "compose") else (),
            cognitive_profile=asdict(profile(family)) if family in FAMILIES else {}),
            lazy("greg.cognition.cortex", "compose" if family == "compose" else "knowledge" if family == "knowledge" else "solve"))
    return entries
