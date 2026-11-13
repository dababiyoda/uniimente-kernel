# Genome admission v3: pre-registration (2026-10-15)

**Status:** pre-registered. Every file in this directory was committed before any held-out instance was generated. `freeze.json` is the machine-checked half of the pre-registration; the run refuses to report if any frozen input differs.

## What is fixed before the run

| Item | Value |
|---|---|
| Run id | `2026-10-15-v3` |
| Held-out seeds | 1200-1229, never generated before this run. The harness refuses seeds spent by v1 (1000-1029) or v2 (1100-1129), development seeds 0-9 and P8's reserved 7000-8059. It also refuses any held-out seed whose finite-pool data was already drawn. |
| Rule | verbatim in `freeze.json` (`inputs.rule`), unchanged since v2 |
| Code | the import closure of the harness and the isolated worker, all of `greg/cognition`, the M4 extract and the dependency versions, each hashed in `freeze.json` |
| Run | once, in a clean worktree at the commit that adds this file, pinned to one CPU core. A crash is recorded, never retried. |
| Arms | candidate `solve`, whose outputs pass through the genome's independent verifier (a refuted output is scored wrong); the declared simple baseline; the declared strongest competitor |
| Statistics | paired one-sided exact sign tests, alpha 0.05; median wall-clock latency in this container |
| Canonical path | one held-out instance per genome through `greg.cognition.cortex.reason`, attached in an evaluation-only registry view. Nothing is attached on any body. |

## Families (24) and why each is measured now

- **15 genomes with no admission verdict.** Of these:
  - 4 are deployable competitors promoted into genomes after v1/v2 superseded their candidates: `pid_simopt` (`basal_pid`), `game_lp_dual` (`game_minimax`), `grid_dijkstra` (`search_astar`) and `knapsack_bnb` (`dp_knapsack`);
  - the others are new Layer 3 packs: `assignment_lsa`, `bimatrix_nash`, `bootstrap_ci`, `critical_path`, `graph_matching`, `mc_expectation`, `mechanism_check`, `milp_optimize`, `min_cost_flow` and `verify_liveness`;
  - the last is `flow_expansion_mcf`, the residual of P6 v4 (F7). Its declared competitor is the deployable graph_then_allocate composition twin, so this run is also the version-bound measurement the founder's F7 audit asked for: is the simpler exact method the canonical genome for capacity expansion?
- **5 genomes whose version changed after their last verdict:** `basal_bayes_filter` 1.0.1, `develop_constraint_release` 1.2.0, `flow_capacity_plan` 1.0.2, `flow_reinforce_greedy` 1.0.1 and `game_minimax` 1.0.2. Their earlier verdicts bind the earlier versions only.
- **4 Layer 2 genomes measured on their native regimes:** `collective_quorum`, `collective_physarum`, `collective_immune` and `collective_flock`.
  - Their candidate `solve` and `verify` are unchanged since v1.
  - Their instance generators, declared competitors (physarum, immune, flock) and scorers (physarum, flock) changed in the Layer 2 native-regime work (`da0ad87`, `d041a3a`, `65b9acc`).
  - The v1 verdicts stand for the old regimes only.
  - A v3 verdict replaces the v1 verdict for routing ("the latest frozen run decides"). Both stay in git.

## What the outcome changes, and what it cannot

- A DEFAULT or NICHE verdict makes a genome routable at its exact version. It does not attach the genome: attaching is the founder's decision.
- A SUPERSEDED, EXPERIMENTAL or REJECTED verdict excludes the genome from routing until a later re-admission. A SUPERSEDED genome whose competitor is deployable names that competitor as an acquisition candidate.
- No result is re-run, re-scored or re-labelled. The README is generated from `results.json` by script after the run. Negative verdicts are reported with the same prominence as positive ones.
- The genome versions are bound by label in the evidence index. The run itself is bound by the code digests in `freeze.json`.
