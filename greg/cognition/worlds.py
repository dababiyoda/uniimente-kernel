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
    "basal_bayes_filter": (SIMULATED, "seeded two-level regime signals; truth is the hidden regime tape"),
    "basal_breaker": (SIMULATED, "seeded up/outage dependency processes; truth is the hidden outage tape"),
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
    "mech_vcg": (SIMULATED, "synthetic bidder values and simulated bidding behaviour"),
    "pid_simopt": (SIMULATED, "seeded FOPDT plant simulations"),
    # mathematical instances: the instance is the problem; truth is computed from it independently
    "assignment_lsa": (MATHEMATICAL, "generated cost matrices; exact optimum"),
    "bimatrix_nash": (MATHEMATICAL, "generated bimatrix games; equilibria checked exactly"),
    "binpack_cpsat": (MATHEMATICAL, "planted bin-packing instances; optimum known by construction"),
    "blackbox_multistart_lbfgsb": (MATHEMATICAL, "declared shifted test objectives; known minimum"),
    "collective_aco": (MATHEMATICAL, "generated TSP instances; Held-Karp or reference tours"),
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
    "game_lp_dual": (MATHEMATICAL, "generated zero-sum games; LP value"),
    "game_minimax": (MATHEMATICAL, "generated zero-sum games; LP value"),
    "graph_matching": (MATHEMATICAL, "generated graphs; exact maximum matching"),
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
    "synth_cegis": (MATHEMATICAL, "planted bounded synthesis tasks; exhaustive check"),
    "verify_liveness": (MATHEMATICAL, "declared transition systems; exhaustive check"),
    "verify_modelcheck": (MATHEMATICAL, "declared transition systems; exhaustive check"),
}

# P6 composition-lift families, as each frozen run's own ``limits`` describes them.
P6_FAMILIES = {
    "F1": (SIMULATED, "constructed to need composition; truth assumes calibrated lognormal intervals"),
    "F2": (SIMULATED, "constructed to need composition; truth is the generator's hidden effects"),
    "F2R": (SIMULATED, "constructed to need two intelligences; truth is the generator's hidden effects"),
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
