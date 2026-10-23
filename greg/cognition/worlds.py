"""The kind of world each frozen held-out benchmark measured competence on (directive 2026-10-07, section 31.17).

A positive held-out verdict says how a mechanism did on its benchmark; what that verdict supports depends on where
the benchmark's instances and truth came from. scripts/mind_status.py labels from this declaration, never from a
genome's own evidence-type token (a heuristic trace can come from a simulated outage process and a simulation
token does not decide whether the instance was the whole problem):

  natural_data           recorded real data, with real outcomes or the exact optimum of a declared problem on
                         real inputs (M4 series, bank call arrivals, SNDlib topologies)
  mathematical_instance  the generated instance is the whole problem and the truth is computed from it by an
                         independent exact or reference method (optimisation, games, verification, integrals of
                         declared distributions, decisions under a declared prior)
  simulated_world        a seeded generative model standing in for a process: the truth is the generator's hidden
                         state, parameter or outcome (plants, signals, reward, outage or bidder-value processes,
                         structural causal models, sampled populations), or a P6 family constructed to need
                         composition. Competence there says nothing yet about the real process it imitates.

``GENOMES`` covers every executable genome (tests/unit/test_mind_status.py fails on a genome without one and checks
the declarations against the instance generators); ``P6_FAMILIES`` covers every family a frozen P6 run measured;
``ORGANS`` is empty because no cortex organ has a frozen per-organ verdict. An undeclared benchmark is never treated
as natural or mathematical. Data only: nothing here registers, routes or authorises anything.
"""
from __future__ import annotations

WORLDS = ("natural_data", "mathematical_instance", "simulated_world")
NATURAL, MATHEMATICAL, SIMULATED = WORLDS

GENOMES = {
    # natural data
    "forecast_quantile": (NATURAL, "M4 Weekly series sampled from a finite pool of recorded data, scored on their "
                                   "real continuations"),
    # simulated worlds: truth is a hidden state, parameter or outcome of a seeded generator
    "basal_bandit": (SIMULATED, "seeded Bernoulli reward processes; truth is the generator's hidden arm means"),
    "mdl_model_select": (SIMULATED, "seeded noisy polynomial data; truth is the generator's hidden degree and a "
                                    "held-back split it never shows"),
    "forecast_judgment_pool": (SIMULATED, "seeded forecaster panels over Gaussian information blocks; truth is the "
                                          "generator's event outcomes and true probabilities"),
    "forecast_scenarios": (SIMULATED, "seeded regime-switching AR and jump processes; truth is the generator's "
                                      "conditional futures"),
    "forecast_recalibration": (SIMULATED, "seeded distorted judgments; truth is the generator's true "
                                          "probabilities"),
    "basal_bayes_filter": (SIMULATED, "seeded two-level regime signals; truth is the hidden regime tape"),
    "basal_nlms": (SIMULATED, "seeded linear streams (stationary, drifting, switching, heavy-tailed noise, correlated "
                              "features); truth is the generator's realised targets"),
    "basal_token_bucket": (SIMULATED, "seeded arrival processes (Poisson, bursty, diurnal) with sampled request "
                                      "values; truth is the offline optimum of the generated stream"),
    "develop_diffusion": (SIMULATED, "planted-partition graphs with seeded labels; truth is the generator's hidden "
                                     "classes"),
    "basal_hopfield": (SIMULATED, "seeded random or biased binary patterns and a cue corrupted by random flips; truth "
                                  "is the hidden source pattern"),
    "develop_ca_repair": (SIMULATED, "seeded elementary-CA space-time patterns with erased holes; truth is the hidden "
                                     "original pattern"),
    "basal_breaker": (SIMULATED, "seeded up/outage dependency processes; truth is the hidden outage tape"),
    "basal_cusum_detect": (SIMULATED, "seeded Gaussian or Student-t streams with a planted mean shift; truth is the "
                                      "hidden change point"),
    "basal_hamming_correct": (SIMULATED, "seeded random data blocks through a simulated bit-flip channel; truth is the "
                                         "hidden original data"),
    "control_robust_tube": (SIMULATED, "seeded linear plant models with a declared disturbance box; truth is the exact "
                                       "worst case over every disturbance vertex sequence of the model"),
    "basal_hysteresis": (SIMULATED, "seeded two-level regime signals; truth is the hidden regime tape"),
    "basal_kalman": (SIMULATED, "seeded DWNA target tracks; truth is the hidden true track"),
    "basal_pid": (SIMULATED, "seeded FOPDT plant simulations"),
    "bayes_interval": (SIMULATED, "binomial samples from a hidden true proportion"),
    "bootstrap_ci": (SIMULATED, "samples from lognormal, exponential and Pareto populations; truth is the "
                                "population parameter"),
    "causal_backdoor": (SIMULATED, "data from generating structural causal models; truth is the model's effect"),
    "collective_flock": (SIMULATED, "simulated agents on a ring"),
    "collective_immune": (SIMULATED, "multivariate-normal self samples with planted anomalies"),
    "collective_market": (SIMULATED, "synthetic lognormal private values"),
    "collective_quorum": (SIMULATED, "seeded observer panels with shared noise; truth is the hidden state"),
    "control_mpc": (SIMULATED, "simulated double-integrator plant"),
    "crowd_weighted_vote": (SIMULATED, "simulated crowds of seeded worker types; truth is the hidden item labels"),
    "develop_repair": (SIMULATED, "simulated TARGET_FORM_001 lattices with seeded damage and controller failures"),
    "develop_repair_hybrid": (SIMULATED, "develop_repair's simulated TARGET_FORM_001 lattices (same generator) with "
                                         "seeded damage and controller failures"),
    "mech_vcg": (SIMULATED, "synthetic bidder values and simulated bidding behaviour"),
    "pid_simopt": (SIMULATED, "seeded FOPDT plant simulations"),
    # mathematical instances: the instance is the problem; truth is computed from it independently
    "assignment_lsa": (MATHEMATICAL, "generated cost matrices; exact optimum"),
    "bimatrix_nash": (MATHEMATICAL, "generated bimatrix games; equilibria checked exactly"),
    "binpack_cpsat": (MATHEMATICAL, "planted bin-packing instances; optimum known by construction"),
    "blackbox_multistart_lbfgsb": (MATHEMATICAL, "declared shifted test objectives; known minimum"),
    "collective_aco": (MATHEMATICAL, "generated TSP instances; Held-Karp or reference tours"),
    "collective_auction": (MATHEMATICAL, "generated task-agent value matrices; exact optimum by the transportation "
                                         "LP"),
    "community_louvain": (MATHEMATICAL, "planted stochastic block models; quality is the recomputed modularity"),
    "collective_physarum": (MATHEMATICAL, "generated Steiner network instances; reference heuristics"),
    "critical_path": (MATHEMATICAL, "generated project networks; exact longest path"),
    "decision_preposterior": (MATHEMATICAL, "structural recomputation on generated posteriors"),
    "develop_constraint_release": (MATHEMATICAL, "generated tardiness instances; exact DP optimum"),
    "dp_knapsack": (MATHEMATICAL, "generated knapsack instances; exact optimum"),
    "flow_capacity_plan": (MATHEMATICAL, "structural translation checks on generated networks"),
    "flow_expansion_mcf": (MATHEMATICAL, "generated relay networks; exact optimum"),
    "flow_maxflow": (MATHEMATICAL, "generated digraphs; exact max flow"),
    "flow_reinforce_greedy": (MATHEMATICAL, "generated relay networks; exact optimum"),
    "formal_property_search": (MATHEMATICAL, "generated integer functions with a planted bug or a bug-free decoy; truth "
                                             "by construction (a re-executed witness, or no bug)"),
    "game_lp_dual": (MATHEMATICAL, "generated zero-sum games; LP value"),
    "game_minimax": (MATHEMATICAL, "generated zero-sum games; LP value"),
    "graph_matching": (MATHEMATICAL, "generated graphs; exact maximum matching"),
    "graph_node_cut_exact": (MATHEMATICAL, "generated dependency-like digraphs; exact minimum vertex cut "
                                           "(Menger augmenting paths)"),
    "grid_dijkstra": (MATHEMATICAL, "generated weighted grids; exact shortest path"),
    "info_experiment": (MATHEMATICAL, "a declared prior and likelihood tables; scenarios drawn from that prior"),
    "knapsack_bnb": (MATHEMATICAL, "generated knapsack instances; exact optimum"),
    "mc_expectation": (MATHEMATICAL, "expectations of declared distributions; analytic truth"),
    "maxsat_cpsat": (MATHEMATICAL, "generated weighted MaxSAT instances; exact optimum by an independent MILP"),
    "mc_importance": (MATHEMATICAL, "Gamma upper tails; truth from the closed-form survival function"),
    "mechanism_check": (MATHEMATICAL, "declared direct mechanisms; exhaustive check"),
    "milp_optimize": (MATHEMATICAL, "generated integer programmes; exact optimum"),
    "min_cost_flow": (MATHEMATICAL, "generated flow networks; exact optimum"),
    "newsvendor_compile": (MATHEMATICAL, "structural translation checks on generated scenario sets"),
    "queue_erlang": (MATHEMATICAL, "declared M/M/c parameters; exact Erlang C"),
    "reconcile_qp": (MATHEMATICAL, "generated noisy balances; exact QP optimum by exhaustive face enumeration"),
    "search_astar": (MATHEMATICAL, "generated weighted grids; exact shortest path"),
    "search_beam": (MATHEMATICAL, "generated flow-shop instances; quality is the makespan against Taillard's lower "
                                  "bound"),
    "search_ida_star": (MATHEMATICAL, "generated sliding-tile positions; exact shortest plan by exhaustive search"),
    "search_mcts": (MATHEMATICAL, "Hex positions from seeded random play; exact winning moves by exhaustive solve"),
    "synth_cegis": (MATHEMATICAL, "planted bounded synthesis tasks; exhaustive check"),
    "verify_liveness": (MATHEMATICAL, "declared transition systems; exhaustive check"),
    "verify_modelcheck": (MATHEMATICAL, "declared transition systems; exhaustive check"),
    "evo_ga_factored": (MATHEMATICAL, "generated factored landscapes (NK, deceptive traps); exact optimum for traps "
                                      "(by construction) and adjacent NK (dynamic programming), the sum of table "
                                      "maxima for random NK"),
    "evo_map_elites": (MATHEMATICAL, "declared planar arms; QD-score over the exactly computed reachable cells"),
    "graph_betweenness_topk": (MATHEMATICAL, "generated graphs; exact betweenness by an independent reference "
                                             "Brandes"),
    "prove_resolution": (MATHEMATICAL, "generated propositional and ground clause sets (pigeonhole, chains, random "
                                       "CNF); entailment decided independently by Z3"),
    "convex_qp_dual": (MATHEMATICAL, "generated dense convex QPs under linear inequalities; optimum by a long SLSQP "
                                     "run polished by an exact active-set KKT iteration"),
    "game_repeated_sustain": (MATHEMATICAL, "generated stage games (prisoner's dilemmas, discrete Cournot, random); "
                                            "exact critical discount from an independent Z3 equilibrium enumeration"),
    "game_nash_bargaining": (MATHEMATICAL, "generated payoff polytopes (random hulls, sampled concave frontiers); "
                                           "exact solution by enumerating every vertex simplex"),
    "game_stackelberg_commit": (MATHEMATICAL, "generated security, inspection and random games; leader optimum by "
                                              "independent HiGHS linear programs"),
    "evo_novelty_search": (MATHEMATICAL, "generated grid mazes of declared kinds (deceptive by design or not); exact "
                                         "maze distance field by BFS"),
    "hyper_select_lowlevel": (MATHEMATICAL, "planted zero-slack bin-packing instances; optimum known by construction "
                                            "(equal to the volume bound)"),
    "develop_differentiate": (MATHEMATICAL, "generated graphs (geometric, small-world, holed grids, random); exact "
                                            "pattern check, CP-SAT reference leader optimum and exact component "
                                            "radii"),
}

# P6 composition-lift families, as each frozen run's own ``limits`` describes them.
P6_FAMILIES = {
    "F1": (SIMULATED, "constructed to need composition; truth assumes calibrated lognormal intervals"),
    "F2": (SIMULATED, "constructed to need composition; truth is the generator's hidden effects"),
    "F2R": (SIMULATED, "constructed to need two intelligences; truth is the generator's hidden effects"),
    "F2b": (SIMULATED, "PR #155 lineage: F2's generator on seeds 25-72, a subset of F2R's 25-88 (a same-instance "
                       "re-run, not fresh seeds); truth is the generator's hidden effects"),
    "F3": (MATHEMATICAL, "constructed to need two intelligences; truth is the exact optimum"),
    "F4": (SIMULATED, "constructed to need two intelligences; truth is the Bayes-optimal action under the declared "
                      "Beta(1,1) prior, not the hidden parameter: in realised value the composition is worse (-55.4 "
                      "against the uninformed constituent's -20.3), and the constituent was denied the observed "
                      "evidence"),
    "F5": (NATURAL, "real M4 data and real outcomes; the newsvendor decision layer is declared"),
    "F6": (NATURAL, "real bank call arrivals and real outcomes; the staffing decision layer is declared"),
    "F7": (NATURAL, "real SNDlib topologies, lengths, demands and loads; truth is the exact optimum of the declared "
                    "planning problem"),
    "F8": (NATURAL, "real NYC 2015 pickups and real outcomes (TLC records via FOIL); the staffing decision layer and the "
                    "Erlang C requirement are declared"),
}

ORGANS: dict[str, tuple[str, str]] = {}

_TABLES = {"genome": GENOMES, "p6_family": P6_FAMILIES, "organ": ORGANS}


def world(kind: str, key: str) -> str | None:
    """The declared benchmark world of a genome family, P6 family or cortex organ id; None when undeclared."""
    entry = _TABLES[kind].get(key)
    return entry[0] if entry else None
