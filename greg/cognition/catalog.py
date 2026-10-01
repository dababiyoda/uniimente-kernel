"""Cognitive metadata extends CapabilityGenome; entries alone are never completion."""
from dataclasses import asdict

from .contracts import CognitiveCapabilityProfile


# family -> (layer, operations, epistemic classes, proof class, dependency)
FAMILIES = {
    "micro": (1, ("setpoint",), ("physical",), "pattern_evidence", None),
    "exact": (3, ("calculate", "polynomial"), ("arithmetic",), "exact_calculation", "sympy"),
    "estimation": (3, ("estimate",), ("estimate",), "bounded_estimate", None),
    "formal": (3, ("constraints",), ("deductive", "constraint_feasibility"), "formal_model", "z3-solver"),
    "optimization": (3, ("optimize",), ("optimization",), "optimization_certificate", "ortools"),
    "graph": (3, ("shortest_path",), ("optimization",), "search_trace", "networkx"),
    "search": (3, ("state_search",), ("optimization",), "search_trace", "networkx"),
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


def profile(family):
    layer, operations, classes, proof, _ = FAMILIES[family]
    return CognitiveCapabilityProfile(family=family, layer=layer, operations=operations,
                                     epistemic_classes=classes, proof_class=proof,
                                     deterministic=family not in ("semantic",),
                                     latency_estimate_seconds=1.0 if family in ("formal", "optimization", "game", "evolutionary", "semantic") else .1)


def builtin_entries(manifest_type, lazy):
    entries = {}
    for family in (*FAMILIES, "solve", "compose", "knowledge"):
        computational = family not in ("knowledge",)
        entries["cognition." + family] = (manifest_type(
            capability_id="cognition." + family, version="0.1.0", provider="greg-builtin",
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
