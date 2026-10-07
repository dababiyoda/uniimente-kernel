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

# Existing alternative implementations retain their code and lineage. Cataloguing
# never silently activates the P5+ repertoire on a new body.
SEED_FAMILIES = frozenset(("micro", "exact", "estimation", "formal", "optimization", "causal", "evidence", "semantic"))

def initial_state(capability_id):
    family = capability_id.removeprefix("cognition.")
    return "VERIFIED" if capability_id.startswith("cognition.") and family in FAMILIES and family not in SEED_FAMILIES else "ATTACHED"


def profile(family):
    layer, operations, classes, proof, _ = FAMILIES[family]
    return CognitiveCapabilityProfile(family=family, layer=layer, operations=operations,
                                     epistemic_classes=classes, proof_class=proof,
                                     deterministic=family not in ("semantic",),
                                     latency_estimate_seconds=1.0 if family in ("formal", "optimization", "game", "evolutionary", "semantic") else .1)


# The Polyintelligence Cortex (PR #141) on the same registry: one router manifest (layer 5)
# and one manifest per executable cortex organ (layer 3). Each is an ordinary GREG
# capability: founder CAPABILITY_DETACH withholds the organ from cortex routing.
# capability id -> (version, epistemic classes, deterministic, network, description)
CORTEX_ENTRIES = {
    "cognition.cortex": ("0.2.1", ("constraint_feasibility", "deductive", "optimization", "estimate", "causal",
                                   "prediction", "semantic", "strategic", "unresolved"), True, "egress-allowlist",
                         "Cortex router: geometry, hard eligibility, two formal engines, verifier, typed receipt"),
    "cognition.cortex.formal.z3": ("0.2.0", ("deductive", "constraint_feasibility", "optimization", "arithmetic"),
                                   True, "none", "Z3 feasibility, entailment and certified optimization"),
    "cognition.cortex.optimization.cpsat": ("0.2.0", ("deductive", "constraint_feasibility", "optimization"), True,
                                            "none", "OR-Tools CP-SAT on the same model; independently re-checked"),
    "cognition.cortex.estimation.fermi": ("0.1.0", ("estimate",), True, "none",
                                          "Unit-checked Fermi decomposition with dependence and sensitivity"),
    "cognition.cortex.evidence_causal": ("0.1.0", ("semantic", "prediction", "causal", "physical"), True, "none",
                                         "Evidence assessment and identification-gated causal estimation"),
    "cognition.cortex.semantic": ("0.1.0", ("semantic", "strategic"), False, "egress-allowlist",
                                  "Source-quoted synthesis through the founder-selected local model only"),
    "cognition.cortex.deterrence.accountability": ("0.1.0", ("strategic",), True, "none",
                                                   "Lawful deterrence: Becker condition, coercion refused"),
    "cognition.cortex.extraction.schedule": ("0.1.0", ("semantic", "constraint_feasibility", "optimization"), False,
                                             "egress-allowlist", "Bounded scheduling request in words -> audited "
                                             "formal model (controlled grammar; founder-selected model only)"),
}
CORTEX_VERSIONS = {cid: spec[0] for cid, spec in CORTEX_ENTRIES.items()}


def cortex_profile(capability_id):
    version, classes, deterministic, _, _ = CORTEX_ENTRIES[capability_id]
    return CognitiveCapabilityProfile(
        family=capability_id.removeprefix("cognition."), layer=5 if capability_id == "cognition.cortex" else 3,
        operations=("cortex",), epistemic_classes=classes, proof_class="cortex_receipt",
        deterministic=deterministic, latency_estimate_seconds=5.0 if capability_id == "cognition.cortex" else 2.0,
        evidence_requirements=("cortex-problem contract: question plus structured payload",),
        uncertainty_model="per proof class inside the cortex receipt",
        state="stateless worker process per problem; bounded CPU and address space",
        abstention_conditions=("missing input, dependency, evidence or authority", "withheld by GREG registry",
                               "formalization incomplete", "not identified"),
        falsification_tests=("tests/unit/test_cortex_formal_engines.py", "tests/unit/test_greg_cortex_bridge.py"),
        lineage=("INTENT-20261001-greg-seed-genome", "PR #141 cortex", "PR #140 GREG cognition"))


def builtin_entries(manifest_type, lazy):
    entries = {}
    for family in (*FAMILIES, "solve", "compose", "knowledge"):
        computational = family not in ("knowledge",)
        entries["cognition." + family] = (manifest_type(
            capability_id="cognition." + family, version="0.2.0", provider="greg-builtin",
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
    for cid, (version, _, _, network, description) in CORTEX_ENTRIES.items():
        entries[cid] = (manifest_type(
            capability_id=cid, version=version, provider="greg-builtin", function=cid, description=description,
            route="internal", consequence_class="read_only", target_prefix="cognition:",
            inputs={"problem_id": "str", "problem": "cortex-problem {question, payload}", "records": "list"},
            outputs={"receipt": "CognitiveReceipt carrying a cortex-receipt/0.2", "authority_created": "false"},
            retry_safe=True, strengthens=("eligibility", "routing", "proof", "settlement"),
            tests=("tests/unit/test_greg_cortex_bridge.py", "tests/integration/test_greg_cortex_mission.py"),
            provenance={"source": "uniimente-kernel/cortex via greg/cognition/bridge.py",
                        "intent": "INTENT-20261001-greg-seed-genome"},
            network=network, egress_allowlist=("127.0.0.1",) if network == "egress-allowlist" else (),
            cognitive_profile=asdict(cortex_profile(cid))), lazy("greg.cognition.cortex", "solve"))
    return entries
