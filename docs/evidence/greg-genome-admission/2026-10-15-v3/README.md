# Held-out genome admission, run 2026-10-15-v3

**What this is:** the third frozen admission run. It covers 24 families on fresh held-out seeds. Every number in the tables below was copied from `results.json` by script (`make_readme_tables.py`, listed under *Reproduce*). Nothing was re-run, re-scored or re-labelled.

> **Errata:** an independent review on 2026-10-15 corrected several statements in this README. The original wording is kept below, and each correction is listed under *Errata (2026-10-15 independent review)* at the end. The frozen files are unchanged.

**Why it ran:** `PREREGISTRATION.md` in this directory, committed with `freeze.json` in `878f76c` before any held-out instance was generated. The 24 families are:
- 15 genomes with no verdict;
- 5 genomes whose version changed after their last verdict;
- the 4 Layer 2 genomes, measured on their native regimes.

## Protocol

| Item | Value |
|---|---|
| Freeze | `freeze.json` (sha256 `a50573cb...`). It hashes 117 code files: the import closure of the harness and the isolated worker, and all of `greg/cognition`. It also records the M4 extract, the requirement files, the dependency versions, the rule and the seeds. |
| Run | once, in a clean worktree at `878f76c`, pinned to one CPU core, exit 0. `run.log` is its console output. Its two `HighsMipSolverData::...` lines are HiGHS writing to native stdout. They do not enter `results.json`. |
| Held-out seeds | 1200-1229, never generated before this run. The harness refused nothing at freeze: no spent, development or P8-reserved seed, and no reused finite-pool data. |
| Arms | candidate `solve` (any output its independent verifier refutes is scored wrong), simple baseline, strongest declared competitor |
| Statistics | paired one-sided exact sign tests, alpha 0.05; median wall-clock latency in this container |
| Canonical path | one held-out instance per genome through `greg.cognition.cortex.reason`, attached in an evaluation-only registry view. All 24 were STRUCTURALLY_VERIFIED, and none created authority. |

The rule, unchanged since v2, is quoted verbatim in `results.json` and `freeze.json`.

## Results (scripted from `results.json`)

- **Source commit:** `878f76c`; freeze `sha256:a50573cbddce05f8...`; Linux-6.18.44-fc-v114-x86_64-with-glibc2.39, Python 3.13.16; finished 2026-10-15T13:10:36.693865+00:00.

| Layer | Genome | Version | Status | Cand c/w/a | Base wrong | Comp wrong | vs baseline | vs competitor | ms cand / comp | Smoke |
|---|---|---|---|---|---|---|---|---|---|---|
| L1 | `basal_bayes_filter` | 1.0.1 | **NICHE_CAPABILITY** | 30/0/0 | 10 | 0 | 11-0 (p=0.000488) | 7-3 (p_worse=0.945) | 63.77 / 1.18 | STRUCTURALLY_VERIFIED |
| L2 | `collective_flock` | 1.0.2 | **SUPERSEDED** | 25/0/5 | 30 | 0 | 30-0 (p=0) | 0-29 (p_worse=0) | 23.25 / 759.25 | STRUCTURALLY_VERIFIED |
| L2 | `collective_immune` | 1.0.2 | **NICHE_CAPABILITY** | 30/0/0 | 2 | 0 | 28-2 (p=0) | 13-11 (p_worse=0.729) | 216.63 / 4.77 | STRUCTURALLY_VERIFIED |
| L2 | `collective_physarum` | 1.0.1 | **NICHE_CAPABILITY** | 30/0/0 | 0 | 0 | 19-9 (p=0.0436) | 8-16 (p_worse=0.0758) | 58.29 / 8.69 | STRUCTURALLY_VERIFIED |
| L2 | `collective_quorum` | 1.0.1 | **NICHE_CAPABILITY** | 20/4/6 | 21 | 8 | 17-1 (p=7.2e-05) | 4-2 (p_worse=0.891) | 0.19 / 0.06 | STRUCTURALLY_VERIFIED |
| L3 | `assignment_lsa` | 1.0.0 | **SUPERSEDED** | 30/0/0 | 30 | 0 | 30-0 (p=0) | 0-0 (p_worse=1) | 3.22 / 1.49 | STRUCTURALLY_VERIFIED |
| L3 | `bimatrix_nash` | 1.0.0 | **DEFAULT_FOR_GEOMETRY** | 30/0/0 | 0 | 0 | 10-0 (p=0.000977) | 11-0 (p_worse=1) | 10.81 / 1.60 | STRUCTURALLY_VERIFIED |
| L3 | `bootstrap_ci` | 1.0.0 | **REJECTED** | 26/4/0 | 3 | 4 | 18-12 (p=0.181) | 5-18 (p_worse=0.00531) | 3.66 / 2.95 | STRUCTURALLY_VERIFIED |
| L3 | `critical_path` | 1.0.0 | **DEFAULT_FOR_GEOMETRY** | 30/0/0 | 30 | 0 | 30-0 (p=0) | 0-0 (p_worse=1) | 0.45 / 0.99 | STRUCTURALLY_VERIFIED |
| L3 | `flow_capacity_plan` | 1.0.2 | **COMPOSITION_ONLY** | 30/0/0 | 0 | 0 | 30-0 (p=0) | 30-0 (p_worse=1) | 0.11 / 0.00 | STRUCTURALLY_VERIFIED |
| L3 | `flow_expansion_mcf` | 1.0.0 | **DEFAULT_FOR_GEOMETRY** | 30/0/0 | 11 | 0 | 11-0 (p=0.000488) | 0-0 (p_worse=1) | 0.66 / 4.57 | STRUCTURALLY_VERIFIED |
| L3 | `flow_reinforce_greedy` | 1.0.1 | **SUPERSEDED** | 19/11/0 | 30 | 0 | 29-0 (p=0) | 0-11 (p_worse=0.000488) | 1.46 / 5.80 | STRUCTURALLY_VERIFIED |
| L3 | `game_lp_dual` | 1.0.0 | **DEFAULT_FOR_GEOMETRY** | 30/0/0 | 0 | 0 | 0-0 (p=1) | 0-0 (p_worse=1) | 0.57 / 1.86 | STRUCTURALLY_VERIFIED |
| L3 | `game_minimax` | 1.0.2 | **SUPERSEDED** | 30/0/0 | 18 | 0 | 18-0 (p=4e-06) | 0-0 (p_worse=1) | 4.59 / 2.56 | STRUCTURALLY_VERIFIED |
| L3 | `graph_matching` | 1.0.0 | **DEFAULT_FOR_GEOMETRY** | 30/0/0 | 28 | 0 | 28-0 (p=0) | 0-0 (p_worse=1) | 5.35 / 9.93 | STRUCTURALLY_VERIFIED |
| L3 | `grid_dijkstra` | 1.0.0 | **EXPERIMENTAL** | 30/0/0 | 0 | 0 | 0-0 (p=1) | 0-0 (p_worse=1) | 1.33 / 11.45 | STRUCTURALLY_VERIFIED |
| L3 | `knapsack_bnb` | 1.0.0 | **DEFAULT_FOR_GEOMETRY** | 30/0/0 | 0 | 0 | 0-0 (p=1) | 0-0 (p_worse=1) | 0.12 / 2.00 | STRUCTURALLY_VERIFIED |
| L3 | `mc_expectation` | 1.0.0 | **NICHE_CAPABILITY** | 29/1/0 | 2 | 2 | 22-8 (p=0.00806) | 5-25 (p_worse=0.000162) | 2.44 / 11.68 | STRUCTURALLY_VERIFIED |
| L3 | `mechanism_check` | 1.0.0 | **DEFAULT_FOR_GEOMETRY** | 30/0/0 | 8 | 0 | 13-0 (p=0.000122) | 0-0 (p_worse=1) | 1.82 / 77.26 | STRUCTURALLY_VERIFIED |
| L3 | `milp_optimize` | 1.0.0 | **SUPERSEDED** | 30/0/0 | 13 | 0 | 13-0 (p=0.000122) | 0-0 (p_worse=1) | 26.61 / 3.82 | STRUCTURALLY_VERIFIED |
| L3 | `min_cost_flow` | 1.0.0 | **DEFAULT_FOR_GEOMETRY** | 30/0/0 | 20 | 0 | 30-0 (p=0) | 0-0 (p_worse=1) | 0.45 / 1.49 | STRUCTURALLY_VERIFIED |
| L3 | `pid_simopt` | 1.0.0 | **DEFAULT_FOR_GEOMETRY** | 30/0/0 | 0 | 0 | 29-1 (p=0) | 14-15 (p_worse=0.5) | 133.12 / 367.67 | STRUCTURALLY_VERIFIED |
| L3 | `verify_liveness` | 1.0.0 | **DEFAULT_FOR_GEOMETRY** | 30/0/0 | 4 | 0 | 9-0 (p=0.00195) | 0-0 (p_worse=1) | 0.93 / 2.23 | STRUCTURALLY_VERIFIED |
| L4 | `develop_constraint_release` | 1.2.0 | **DEFAULT_FOR_GEOMETRY** | 30/0/0 | 0 | 0 | 24-2 (p=5e-06) | 10-13 (p_worse=0.339) | 73.02 / 62.27 | STRUCTURALLY_VERIFIED |

Against each genome's previous verdict (from the evidence index committed before this run):

| Genome | previous version | previous status | previous evidence | v3 version | v3 status |
|---|---|---|---|---|---|
| `assignment_lsa` | - | no verdict | - | 1.0.0 | SUPERSEDED |
| `basal_bayes_filter` | 1.0.0 | DEFAULT_FOR_GEOMETRY | `2026-10-14-v2` | 1.0.1 | NICHE_CAPABILITY |
| `bimatrix_nash` | - | no verdict | - | 1.0.0 | DEFAULT_FOR_GEOMETRY |
| `bootstrap_ci` | - | no verdict | - | 1.0.0 | REJECTED |
| `collective_flock` | 1.0.2 | SUPERSEDED | `2026-10-13-v1` | 1.0.2 | SUPERSEDED |
| `collective_immune` | 1.0.2 | EXPERIMENTAL | `2026-10-13-v1` | 1.0.2 | NICHE_CAPABILITY |
| `collective_physarum` | 1.0.1 | NICHE_CAPABILITY | `2026-10-13-v1` | 1.0.1 | NICHE_CAPABILITY |
| `collective_quorum` | 1.0.1 | EXPERIMENTAL | `2026-10-13-v1` | 1.0.1 | NICHE_CAPABILITY |
| `critical_path` | - | no verdict | - | 1.0.0 | DEFAULT_FOR_GEOMETRY |
| `develop_constraint_release` | 1.1.1 | NICHE_CAPABILITY | `2026-10-14-v2` | 1.2.0 | DEFAULT_FOR_GEOMETRY |
| `flow_capacity_plan` | 1.0.1 | COMPOSITION_ONLY | `2026-10-13-v1` | 1.0.2 | COMPOSITION_ONLY |
| `flow_expansion_mcf` | - | no verdict | - | 1.0.0 | DEFAULT_FOR_GEOMETRY |
| `flow_reinforce_greedy` | 1.0.0 | SUPERSEDED | `2026-10-13-v1` | 1.0.1 | SUPERSEDED |
| `game_lp_dual` | - | no verdict | - | 1.0.0 | DEFAULT_FOR_GEOMETRY |
| `game_minimax` | 1.0.1 | SUPERSEDED | `2026-10-13-v1` | 1.0.2 | SUPERSEDED |
| `graph_matching` | - | no verdict | - | 1.0.0 | DEFAULT_FOR_GEOMETRY |
| `grid_dijkstra` | - | no verdict | - | 1.0.0 | EXPERIMENTAL |
| `knapsack_bnb` | - | no verdict | - | 1.0.0 | DEFAULT_FOR_GEOMETRY |
| `mc_expectation` | - | no verdict | - | 1.0.0 | NICHE_CAPABILITY |
| `mechanism_check` | - | no verdict | - | 1.0.0 | DEFAULT_FOR_GEOMETRY |
| `milp_optimize` | - | no verdict | - | 1.0.0 | SUPERSEDED |
| `min_cost_flow` | - | no verdict | - | 1.0.0 | DEFAULT_FOR_GEOMETRY |
| `pid_simopt` | - | no verdict | - | 1.0.0 | DEFAULT_FOR_GEOMETRY |
| `verify_liveness` | - | no verdict | - | 1.0.0 | DEFAULT_FOR_GEOMETRY |

Native subregions against the competitor (reported in receipts, never a status):

| Genome | Subregion | n | wins-losses-ties | p_better | p_worse |
|---|---|---:|---|---:|---:|
| `assignment_lsa` | few_distinct_costs | 6 | 0-0-6 | 1 | 1 |
| `assignment_lsa` | rectangular | 6 | 0-0-6 | 1 | 1 |
| `assignment_lsa` | square_large | 13 | 0-0-13 | 1 | 1 |
| `assignment_lsa` | square_small | 5 | 0-0-5 | 1 | 1 |
| `basal_bayes_filter` | high_noise | 9 | 7-2-0 | 0.0898 | 0.98 |
| `basal_bayes_filter` | low_noise | 21 | 0-1-20 | 1 | 0.5 |
| `bimatrix_nash` | multi_pure | 13 | 10-0-3 | 0.000977 | 1 |
| `bimatrix_nash` | no_pure | 9 | 0-0-9 | 1 | 1 |
| `bimatrix_nash` | one_pure | 8 | 1-0-7 | 0.5 | 1 |
| `bootstrap_ci` | mean_skew_1_3 | 10 | 2-8-0 | 0.989 | 0.0547 |
| `bootstrap_ci` | mean_skew_above_3 | 4 | 0-4-0 | 1 | 0.0625 |
| `bootstrap_ci` | mean_skew_below_1 | 1 | 0-1-0 | 1 | 0.5 |
| `bootstrap_ci` | median_skew_1_3 | 12 | 3-2-7 | 0.5 | 0.812 |
| `bootstrap_ci` | median_skew_above_3 | 1 | 0-1-0 | 1 | 0.5 |
| `bootstrap_ci` | median_skew_below_1 | 2 | 0-2-0 | 1 | 0.25 |
| `collective_flock` | agent_dropout | 10 | 0-10-0 | 1 | 0.000977 |
| `collective_flock` | four_to_five_agents | 4 | 0-3-1 | 1 | 0.125 |
| `collective_flock` | limited_radius | 10 | 0-10-0 | 1 | 0.000977 |
| `collective_flock` | six_to_eight_agents | 6 | 0-6-0 | 1 | 0.0156 |
| `collective_immune` | annular_self | 7 | 4-1-2 | 0.188 | 0.969 |
| `collective_immune` | low_dim_2_3 | 4 | 0-3-1 | 1 | 0.125 |
| `collective_immune` | mid_dim_4_6 | 4 | 0-4-0 | 1 | 0.0625 |
| `collective_immune` | multimodal_self | 8 | 5-2-1 | 0.227 | 0.938 |
| `collective_immune` | nonconvex_self | 7 | 4-1-2 | 0.188 | 0.969 |
| `collective_physarum` | edge_failure_mid_run | 15 | 6-6-3 | 0.613 | 0.613 |
| `collective_physarum` | high_fault_weight | 7 | 2-4-1 | 0.891 | 0.344 |
| `collective_physarum` | low_fault_weight | 8 | 0-6-2 | 1 | 0.0156 |
| `collective_quorum` | dominant_faction | 4 | 0-1-3 | 1 | 0.5 |
| `collective_quorum` | spread_factions | 6 | 0-0-6 | 1 | 1 |
| `collective_quorum` | wrong_faction_early_decision | 10 | 3-1-6 | 0.312 | 0.938 |
| `collective_quorum` | wrong_faction_late_decision | 10 | 1-0-9 | 0.5 | 1 |
| `critical_path` | deep | 7 | 0-0-7 | 1 | 1 |
| `critical_path` | dense | 8 | 0-0-8 | 1 | 1 |
| `critical_path` | sparse | 15 | 0-0-15 | 1 | 1 |
| `develop_constraint_release` | loose_due_dates | 15 | 3-7-5 | 0.945 | 0.172 |
| `develop_constraint_release` | tight_due_dates | 15 | 7-6-2 | 0.5 | 0.709 |
| `game_lp_dual` | mixed | 18 | 0-0-18 | 1 | 1 |
| `game_lp_dual` | pure_saddle | 12 | 0-0-12 | 1 | 1 |
| `game_minimax` | mixed | 18 | 0-0-18 | 1 | 1 |
| `game_minimax` | pure_saddle | 12 | 0-0-12 | 1 | 1 |
| `graph_matching` | bipartite | 7 | 0-0-7 | 1 | 1 |
| `graph_matching` | general_dense | 4 | 0-0-4 | 1 | 1 |
| `graph_matching` | general_sparse | 13 | 0-0-13 | 1 | 1 |
| `graph_matching` | triangle_clustered | 6 | 0-0-6 | 1 | 1 |
| `grid_dijkstra` | obstacle_uniform | 10 | 0-0-10 | 1 | 1 |
| `grid_dijkstra` | open_weighted | 10 | 0-0-10 | 1 | 1 |
| `grid_dijkstra` | walls_and_mud | 10 | 0-0-10 | 1 | 1 |
| `knapsack_bnb` | strongly_correlated | 7 | 0-0-7 | 1 | 1 |
| `knapsack_bnb` | subset_sum | 7 | 0-0-7 | 1 | 1 |
| `knapsack_bnb` | uncorrelated | 8 | 0-0-8 | 1 | 1 |
| `knapsack_bnb` | weakly_correlated | 8 | 0-0-8 | 1 | 1 |
| `mc_expectation` | discontinuous_d1_3 | 2 | 0-2-0 | 1 | 0.25 |
| `mc_expectation` | discontinuous_d4_8 | 4 | 0-4-0 | 1 | 0.0625 |
| `mc_expectation` | kinked_d1_3 | 2 | 0-2-0 | 1 | 0.25 |
| `mc_expectation` | kinked_d4_8 | 4 | 1-3-0 | 0.938 | 0.312 |
| `mc_expectation` | smooth_d1_3 | 6 | 2-4-0 | 0.891 | 0.344 |
| `mc_expectation` | smooth_d4_8 | 12 | 2-10-0 | 0.997 | 0.0193 |
| `mechanism_check` | first_price | 6 | 0-0-6 | 1 | 1 |
| `mechanism_check` | public_project | 6 | 0-0-6 | 1 | 1 |
| `mechanism_check` | random_mechanism | 3 | 0-0-3 | 1 | 1 |
| `mechanism_check` | rare_fee | 3 | 0-0-3 | 1 | 1 |
| `mechanism_check` | second_price | 6 | 0-0-6 | 1 | 1 |
| `mechanism_check` | second_price_bug | 6 | 0-0-6 | 1 | 1 |
| `milp_optimize` | assignment | 10 | 0-0-10 | 1 | 1 |
| `milp_optimize` | covering | 10 | 0-0-10 | 1 | 1 |
| `milp_optimize` | knapsack | 10 | 0-0-10 | 1 | 1 |
| `min_cost_flow` | rebates | 10 | 0-0-10 | 1 | 1 |
| `min_cost_flow` | transportation | 10 | 0-0-10 | 1 | 1 |
| `min_cost_flow` | transshipment | 10 | 0-0-10 | 1 | 1 |
| `pid_simopt` | balanced | 4 | 1-2-1 | 0.875 | 0.5 |
| `pid_simopt` | delay_dominant | 6 | 4-2-0 | 0.344 | 0.891 |
| `pid_simopt` | lag_dominant | 20 | 9-11-0 | 0.748 | 0.412 |
| `verify_liveness` | counter_reset | 6 | 0-0-6 | 1 | 1 |
| `verify_liveness` | livelock | 6 | 0-0-6 | 1 | 1 |
| `verify_liveness` | peterson_starvation | 6 | 0-0-6 | 1 | 1 |
| `verify_liveness` | random_lts | 6 | 0-0-6 | 1 | 1 |
| `verify_liveness` | round_robin | 6 | 0-0-6 | 1 | 1 |

Refuted candidate outputs per genome: none
Status counts: {'SUPERSEDED': 5, 'NICHE_CAPABILITY': 5, 'DEFAULT_FOR_GEOMETRY': 11, 'REJECTED': 1, 'COMPOSITION_ONLY': 1, 'EXPERIMENTAL': 1}

## What the results mean

- **The founder's F7 question is answered at an exact version.** `flow_expansion_mcf` 1.0.0, budgeted min-cost-flow expansion with a duality certificate, is **DEFAULT_FOR_GEOMETRY** against the deployable graph_then_allocate composition twin (compile + CP-SAT):
  - it ties the composition's quality on all 30 held-out instances at about one seventh of its median latency (0.66 ms against 4.57 ms);
  - it beats its greedy baseline 11-0, and the greedy baseline was wrong on 11.

  On this geometry the simpler exact method is the canonical genome. P6 v4's F7 lift, 92-0 over GREG's repertoire as it then stood, is a lift over a repertoire that lacked this method. It is not evidence that composition beats a single exact intelligence. That frozen result is unchanged; this is the version-bound measurement that puts it in context.
- **Eight DEFAULT verdicts rest on latency, not quality.** The frozen rule lets an equal-quality answer that is at least 1.25x cheaper than its baseline, and no more than 1.25x its competitor's median latency, count as an edge:
  - `game_lp_dual`, `knapsack_bnb`, `critical_path`, `min_cost_flow`, `mechanism_check`, `graph_matching`, `verify_liveness` and `flow_expansion_mcf` tie their competitor on all 30 instances.
  - Several medians are below 2 ms, where the differences are fractions of a millisecond in one container.
  - Read these verdicts as "an exact method as good as its strongest competitor and not slower". They do not mean it beats that competitor.
- **Genomes the rule excludes:**
  - `bootstrap_ci` is **REJECTED**: 4 wrong answers against its normal-approximation baseline's 3. It lost to the percentile bootstrap 5-18.
  - `milp_optimize`, `assignment_lsa` and `game_minimax` are **SUPERSEDED**: they tie a deployable competitor that is at least 1.25x cheaper.
  - `flow_reinforce_greedy` stays SUPERSEDED: 11 wrong against an exact competitor.
  - `collective_flock` stays SUPERSEDED on its native regimes: it lost 0-29 to prioritised space-time planning.
- **A geometry left with no routable genome.** `grid_dijkstra` (promoted from the mechanism that superseded `search_astar` in v1) is **EXPERIMENTAL**:
  - it ties its baseline (`search_astar`'s own A*) on every instance at 1.33 ms against 1.62 ms, which is 1.22x and short of the 1.25x the rule needs;
  - `search_astar` remains SUPERSEDED.

  A grid shortest-path request therefore has no admitted genome. The compiler names the superseding mechanism as an acquisition candidate. This is a rule-boundary outcome, reported as measured.
- **The Layer 2 families on their native regimes.** Three moved up. All four were measured on the generators, competitors and scorers declared after v1.

  | Genome | Status | vs baseline | vs competitor | Notes |
  |---|---|---|---|---|
  | `collective_quorum` | EXPERIMENTAL → NICHE | 17-1 over simple majority | 4-2 over the group-majority competitor | 4 wrong answers against the competitor's 8 |
  | `collective_immune` | EXPERIMENTAL → NICHE | 28-2 | 13-11 against the per-regime competitor (Hotelling or 5-NN conformal), not significant | about 45x slower |
  | `collective_physarum` | stays NICHE | 19-9 | 8-16, not significant | |
  | `collective_flock` | SUPERSEDED | | 0-29 | |

- **Version changes:**
  - `develop_constraint_release` 1.2.0 is **DEFAULT_FOR_GEOMETRY**, up from NICHE at 1.1.1. Against random-restart search it went from 5-15 (p_worse 0.021) to 10-13 (p_worse 0.339): no longer significantly worse, at 1.17x its latency. Random restart still wins more instances. The constraint-release discovery node (P9) stays unmet.
  - `basal_bayes_filter` 1.0.1 fell from DEFAULT to **NICHE_CAPABILITY**. It beat the Schmitt-trigger competitor 7-3 (14-2 at 1.0.0), which is no longer significant, and it is about 54x slower. This draw held 9 high-noise instances against v2's 16, and its edge lives under high noise (7-2 here).
- **No verifier refuted any candidate output.** Three candidates still gave wrong answers: `bootstrap_ci` 4, `collective_quorum` 4 and `mc_expectation` 1. These outputs verified as computed but missed the instance's truth, and the rule scores them wrong. `collective_flock` abstained on 5 instances and gave no wrong answer.

## Replication finding, again

Two families crossed a rule boundary between independent runs:
- `basal_bayes_filter` went DEFAULT → NICHE;
- `develop_constraint_release` went NICHE → DEFAULT, at a new version.

The index keeps every run's status per genome (`history`), so routing and the founder can see that a status moved. As in v2, a status near a boundary is a sample, not a property. The rule is frozen and unchanged by this observation.

## Totals after this run

All 47 executable genomes now carry evidence measured at their current version, and none is routed on stale evidence:
- 23 DEFAULT_FOR_GEOMETRY, 11 NICHE_CAPABILITY, 8 SUPERSEDED, 3 COMPOSITION_ONLY, 1 EXPERIMENTAL, 1 REJECTED;
- **34 admitted** (DEFAULT or NICHE): L1 5, L2 5, L3 22, L4 2.

None is attached. Attaching any genome on the body is the founder's decision; the compiler prepares the ask.

## Reproduce

```
git worktree add /tmp/admit-v3 878f76c && cd /tmp/admit-v3
PYTHONPATH=. taskset -c 1 python -m greg.cognition.genomes.admission --run 2026-10-15-v3
python docs/evidence/greg-genome-admission/2026-10-15-v3/make_readme_tables.py docs/evidence/greg-genome-admission/2026-10-15-v3/results.json <index at 878f76c>
```

The harness refuses with `FROZEN_INPUT_CHANGED` if any frozen input differs, and refuses to overwrite `results.json`.

## Errata (2026-10-15 independent review)

Each item quotes the original wording, which stays in place above, and states the correction. Every number here was recomputed from `results.json`, `freeze.json` and the evidence index at `878f76c`. No frozen file was changed, and nothing was re-run.

1. **Scope of "by script".** Original: "Every number in the tables below was copied from `results.json` by script (`make_readme_tables.py`, listed under *Reproduce*)."
   - The script generates only the section *Results (scripted from `results.json`)*: the source-commit line, the three tables with their captions and the two summary lines. Those 142 lines regenerate byte for byte from `results.json` and the index at `878f76c`.
   - The Layer 2 table under *What the results mean*, and every count in that section's prose, were written by hand. Items 2 to 4 below are errors in those hand-written parts.
2. **Layer 2 movements.** Original: "Three moved up. All four were measured on the generators, competitors and scorers declared after v1."
   - Two moved up: `collective_quorum` and `collective_immune`, each from EXPERIMENTAL to NICHE_CAPABILITY.
   - `collective_physarum` stayed NICHE_CAPABILITY and `collective_flock` stayed SUPERSEDED, as the table under that sentence shows.
   - All four were measured on instance generators changed after v1. Only some of the other components changed, as `PREREGISTRATION.md` declares:
     - the declared competitor changed for physarum, immune and flock;
     - the scorer changed for physarum and flock;
     - `collective_quorum`'s competitor and scorer are unchanged since v1.
3. **`collective_quorum`'s edge over its competitor.** Original table row: "| `collective_quorum` | EXPERIMENTAL → NICHE | 17-1 over simple majority | 4-2 over the group-majority competitor | 4 wrong answers against the competitor's 8 |".
   - All four wins are abstentions on instances where the competitor answered wrongly (seeds 1201, 1210, 1211 and 1222).
   - Both losses are abstentions where the competitor answered correctly (seeds 1200 and 1219).
   - On the competitor's other four wrong answers (seeds 1207, 1213, 1220 and 1225), the candidate was wrong too. It never answered correctly where the competitor erred.
   - It abstained on 6 of 30 instances. Its 4 wrong answers are real: seeds 1207, 1213, 1220 and 1225, listed above. The gap of 4 between those 4 and the competitor's 8 is the four abstentions where the competitor erred.
   - The NICHE_CAPABILITY verdict is the frozen rule's and stands. The edge it records is abstention, not a correct answer.
4. **Wrong answers and abstentions.** Original: "Three candidates still gave wrong answers: `bootstrap_ci` 4, `collective_quorum` 4 and `mc_expectation` 1." and "`collective_flock` abstained on 5 instances and gave no wrong answer."
   - Four candidates gave wrong answers, 20 in all: `flow_reinforce_greedy` 11, `bootstrap_ci` 4, `collective_quorum` 4 and `mc_expectation` 1.
   - Two abstained, 11 times in all: `collective_quorum` on 6 instances and `collective_flock` on 5.
   - This was an inconsistency in the prose, not an omission from the record. The scripted table shows `flow_reinforce_greedy` at 19/11/0 and `collective_quorum` at 20/4/6, and the bullet above the sentence says "`flow_reinforce_greedy` stays SUPERSEDED: 11 wrong".
5. **The canonical-path smoke for `collective_quorum`.** Original: "All 24 were STRUCTURALLY_VERIFIED, and none created authority." The Smoke column also reads STRUCTURALLY_VERIFIED for every genome.
   - Both match the record: the verifier field of every canonical-path record is STRUCTURALLY_VERIFIED, and none created authority.
   - They do not show that `collective_quorum`'s smoke instance abstained. Its record has `abstention_state` ABSTAIN and `proof_type` null.
   - Read it as: 23 smoke runs answered and were STRUCTURALLY_VERIFIED; `collective_quorum`'s abstained. The canonical path reproduced the genome's own abstention on seed 1200, where its held-out row also abstains.
   - `make_readme_tables.py` prints only the verifier field. It is left unchanged so that the committed tables still regenerate byte for byte.
6. **What the eight latency-based DEFAULT verdicts rest on.** Original: "**Eight DEFAULT verdicts rest on latency, not quality.** The frozen rule lets an equal-quality answer that is at least 1.25x cheaper than its baseline, and no more than 1.25x its competitor's median latency, count as an edge:" and "Several medians are below 2 ms, where the differences are fractions of a millisecond in one container."
   - All eight tie their competitor on all 30 instances. DEFAULT rather than NICHE or SUPERSEDED rests on the candidate's median latency being no more than 1.25x the competitor's. The measured ratios run from 0.02 to 0.54.
   - The condition "at least 1.25x cheaper than its baseline" applies to two of the eight. `game_lp_dual` and `knapsack_bnb` also tie their baseline on all 30 instances, and they clear the baseline only by being 6.08x and 3.02x cheaper than it.
   - The other six beat their baseline on quality: `critical_path` 30-0, `min_cost_flow` 30-0, `graph_matching` 28-0, `mechanism_check` 13-0, `flow_expansion_mcf` 11-0 and `verify_liveness` 9-0.
     - Four of these six have a slower median than their baseline: `critical_path`, `min_cost_flow`, `graph_matching` and `mechanism_check`.
   - The candidate-to-competitor latency gap is under 1 ms only for `critical_path` (0.54 ms). It is 1.04-4.58 ms for six genomes and 75.44 ms for `mechanism_check`.
7. **Where `flow_expansion_mcf` was measured.** Original: "On this geometry the simpler exact method is the canonical genome."
   - The 30 held-out instances (seeds 1200-1229) come from the synthetic capacity-expansion generator in `greg/cognition/genomes/flow.py`. It builds layered networks: s, 3-4 relays, 3-4 relays, t, with random capacities, unit costs from 1 to 5 and a budget from 8 to 28.
   - The genome was not run on F7's SNDlib items. The one-seventh latency (0.66 ms against 4.57 ms) and the tie on all 30 instances were measured on the synthetic instances.
   - "This geometry" therefore means the capacity-expansion geometry as that generator samples it.
8. **The freeze and the run.** Original: "It hashes 117 code files: the import closure of the harness and the isolated worker, and all of `greg/cognition`. It also records the M4 extract, the requirement files, ..." and "once, in a clean worktree at `878f76c`".
   - `freeze.json` hashes 117 files. 113 are the Python import closure of the harness and the isolated worker, plus all of `greg/cognition`. The other four are the `FREEZE_EXTRA` entries in `admission.py`: `tools/offline_test.py` (the 114th Python file, outside that closure), the M4 extract and the two requirement files. They are part of the 117, not in addition to it.
   - `results.json` records `source_commit` 878f76c but no dirty-tree state, and the harness had no dirty check. So "clean" and "once" are the operator's statements, not recorded facts.
   - What is enforced: `--run` rehashes every frozen input and would have refused with `FROZEN_INPUT_CHANGED` had any hashed file differed from the freeze.
   - Future runs record `source_dirty` in `results.json`. It lists the frozen files whose bytes differ from their blob at HEAD; see `greg/cognition/genomes/admission.py`.
