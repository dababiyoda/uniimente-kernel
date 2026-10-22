"""The cortex's reserved families as GREG executes them today: the reconciliation record (directive section 31.17).

cortex/genome.py registers ``RESERVED_FAMILIES`` disabled: "Reserved family ...; no executor in the seed
experiment." GREG's one cognition path (greg/cognition/catalog.py, including the IntelligenceGenome library) has
since gained executors for several of those mechanisms. cortex/genome.py is frozen code of the cortex 0.2.1 seed
freeze (cortex/evaluation/freeze-v0.2.1.json; tests/unit/test_cortex_pipeline.py checks the digest), so its
registry keeps the frozen SPECIFIED status: history is not rewritten. This module is the current record beside it.

It applies cortex/genome.py's own convention - "A reserved family later implemented as a seed organ stays
registered as SUPERSEDED lineage" - to a reserved family whose declared mechanism (its failure-diversity key) now
executes on GREG's path: its current status is SUPERSEDED, with lineage naming every executor. The frozen cortex
registry carries that status only when the cortex's next version re-freezes (``frozen_record_behind``).

``EXECUTED_ON_GREG`` names executors as ``cognition.<family>`` (a catalog family) or ``module:symbol``; each note
states the coverage, because executing is not succeeding (admission verdicts live in
docs/evidence/greg-mind-evidence-index.json), and names any partial precursor that is not an executor.
``RESERVED_WITHOUT_EXECUTOR`` says why every other reserved family still has no executor anywhere; a partial
precursor does not execute the declared mechanism.
tests/unit/test_cortex_reserved_drift.py reconciles both tables with ``library.executables()`` and the catalog.

Verified here: nothing; this is data plus a read-only projection. Not verified anywhere: that an executor
implements its reserved mechanism well. Nothing here registers, enables, attaches or routes anything.
"""
from __future__ import annotations

EXECUTED_ON_GREG = {
    "cortex.graph.search": (("cognition.graph", "cognition.search", "cognition.search_astar", "cognition.grid_dijkstra",
                             "cognition.search_ida_star"),
                            "Dijkstra shortest path (networkx), weighted-grid A* and SciPy csgraph grid Dijkstra, and "
                            "memory-bounded IDA* on implicit sliding-puzzle state graphs; cognition.search_beam "
                            "(beam search over flow-shop insertion sequences), cognition.search_mcts (UCT game-tree "
                            "search for Hex moves) and cognition.formal_property_search (counterexample search over a "
                            "typed expression language) are different search mechanisms, not graph path search"),
    "cortex.control.feedback": (("cognition.control", "cognition.basal_pid", "cognition.control_mpc",
                                 "cognition.pid_simopt"),
                                "clamped PID step, SIMC PI tuning, simulation-optimised PI tuning and box-constrained "
                                "linear MPC"),
    "cortex.sequential.bandit": (("cognition.basal_bandit", "cognition.sequential"),
                                 "Thompson sampling and finite-horizon MDP backward induction"),
    "cortex.pattern.anomaly": (("cognition.pattern",), "population z-score anomalies (descriptive only)"),
    "cortex.information.voi": (("cognition.information", "cognition.decision_preposterior",
                                "cognition.info_experiment"),
                               "scenario value of information, beta-binomial preposterior analysis and greedy "
                               "expected-information-gain test selection"),
    "cortex.game.mechanism": (("cognition.game", "cognition.game_minimax", "cognition.game_lp_dual",
                               "cognition.bimatrix_nash", "cognition.mech_vcg", "cognition.mechanism_check",
                               "cognition.game_repeated_sustain", "cognition.game_nash_bargaining",
                               "cognition.game_stackelberg_commit"),
                              "zero-sum matrix games by LP (with a duality certificate), general-sum bimatrix Nash "
                              "equilibria by support enumeration, the VCG multi-unit mechanism, exhaustive "
                              "dominant-strategy incentive-compatibility and participation checks of declared direct "
                              "mechanisms, the critical discount of a two-player repeated game under Nash-reversion "
                              "grim trigger (no optimal penal codes), the two- or three-player Nash bargaining "
                              "solution over a polytope, and the strong Stackelberg leader commitment by multiple "
                              "LPs (one follower type)"),
    "cortex.human.panel": (("cognition.human",),
                           "a typed route to authenticated human judgment: the family records the panel and "
                           "abstains HUMAN_REVIEW_REQUIRED; it never adjudicates"),
    "cortex.exact.symbolic": (("cognition.exact",), "SymPy exact calculation"),
    "cortex.search.heuristic": (("cognition.search_astar",), "A* with an admissible heuristic on weighted grids"),
    "cortex.meta.mental_models": (("greg.cognition.compiler:OPERATORS",),
                                  "typed mental-model operators in the Competency Compiler"),
    "cortex.meta.metaconsensus": (("greg.cognition.verification:metaconsensus",),
                                  "jurisdiction-preserving metaconsensus over receipts; never a majority vote"),
    "cortex.collective.hive_quorum": (("cognition.collective_quorum",),
                                      "evidence accumulation with cross-inhibition and a quorum threshold; "
                                      "cognition.collective (operation quorum) is a partial precursor only: a "
                                      "weighted-vote quorum threshold over independent observers, with no evidence "
                                      "accumulation or cross-inhibition"),
    "cortex.collective.stigmergy": (("cognition.collective_aco",),
                                    "MAX-MIN ant system with evaporating pheromone on symmetric TSP"),
    "cortex.collective.slime_network": (("cognition.collective_physarum",),
                                        "Physarum flux-conductance network design"),
    "cortex.developmental.evolutionary": (("cognition.evolutionary", "greg.cognition.evolution:cycle",
                                           "cognition.evo_ga_factored", "cognition.evo_map_elites"),
                                          "differential evolution over a bounded vector, P8 mutation/crossover "
                                          "of closed configuration spaces under a sealed evaluator, a generational "
                                          "GA on factored binary objectives and MAP-Elites quality-diversity "
                                          "archives; programs are not evolved"),
    "cortex.developmental.program_synthesis": (("cognition.synth_cegis",),
                                               "counterexample-guided synthesis of a fixed template's bounded "
                                               "integer parameters"),
    "cortex.developmental.constraint_release": (("cognition.develop_constraint_release",),
                                                "re-order, re-wire and recombine validated operators of one "
                                                "scheduling pipeline in a sandbox"),
    "cortex.developmental.morphogenetic": (("cognition.develop_repair",),
                                           "bounded local repair on simulated TARGET_FORM_001 lattices; beating a "
                                           "strong centralized baseline with replication (the P10 exit) is not met"),
    "cortex.developmental.mica_field": (("cognition.develop_repair",),
                                        "sink-potential waves and local adoption rules on a simulated lattice"),
}

RESERVED_WITHOUT_EXECUTOR = {
    "cortex.probabilistic.bayes": "conjugate Beta-binomial updates (cognition.probabilistic, "
                                  "cognition.bayes_interval) and exact two-state HMM forward filtering "
                                  "(cognition.basal_bayes_filter) only; no probabilistic-programming executor",
    "cortex.simulation.twin": "cognition.simulation is an uncalibrated iid Bernoulli Monte Carlo and "
                              "cognition.mc_expectation estimates expectations of declared distributions; no twin of "
                              "a strategic or causal system exists",
    "cortex.collective.swarm_pso": "no particle swarm: cognition.collective_flock is local collision-avoidance "
                                   "rules and cognition.evolutionary is differential evolution",
    "cortex.collective.immune": "partial precursors only: cognition.collective_immune is negative-selection "
                                "detection under a fixed false-alarm tolerance, and greg.genesis.Genesis.repair "
                                "quarantines a formed capability that fails in service and re-forms its function "
                                "through Capability Genesis; no anomaly-tolerance family updates its tolerance from "
                                "verified incidents or feeds its detections into that quarantine and repair",
    "cortex.collective.ecology_market": "partial precursors only: cognition.collective_market allocates capacity "
                                        "among tasks by a clock auction, and the Competency Compiler settles each "
                                        "method's outcomes on the body and re-ranks and demotes methods by them "
                                        "(greg.cognition.compiler._settled_competence, _settled_inhibition); methods "
                                        "do not bid for problems, no market allocates problems among methods, and "
                                        "conditional routing was demoted (P4 v3 REGRESSION)",
    "cortex.developmental.molecular_micro": "cognition.micro is a ternary set-point rule with no association or "
                                            "decay",
    "cortex.meta.global_workspace": "no module competition or selective broadcast exists",
    "cortex.meta.active_inference": "no generative-model policy selection exists",
}


def reconciled() -> dict[str, dict]:
    """reserved family -> its frozen cortex record and its current status under the cortex's own convention."""
    from cortex.genome import RESERVED_FAMILIES, SEED_ORGANS, seed_registry
    registry = seed_registry()
    out = {}
    for name in RESERVED_FAMILIES:
        frozen = registry.get(f"{name}@0.1.0").profile
        if name in SEED_ORGANS:
            status, lineage, executors = frozen.lifecycle, list(frozen.lineage), [
                f"{name}@{SEED_ORGANS[name].get('version', '0.1.0')}"]
            reason = None
        elif name in EXECUTED_ON_GREG:
            executors, coverage = EXECUTED_ON_GREG[name]
            status, executors, reason = "SUPERSEDED", list(executors), None
            lineage = list(frozen.lineage) + [
                f"superseded on GREG's cognition path by {', '.join(executors)}: {coverage}"]
        else:
            status, lineage, executors = "SPECIFIED", list(frozen.lineage), []
            reason = RESERVED_WITHOUT_EXECUTOR.get(name)
        out[name] = {"status": status, "lineage": lineage, "executors": executors, "no_executor_reason": reason,
                     "frozen_lifecycle": frozen.lifecycle, "frozen_record_behind": frozen.lifecycle != status,
                     "enabled_in_cortex": frozen.enabled}
    return out
