# Genome admission v4: pre-registration (2026-10-16)

**Status:** pre-registered. This file and `freeze.json` are committed before any held-out instance is generated. The run refuses to report if any frozen input differs.

## What is fixed before the run

| Item | Value |
|---|---|
| Run id | `2026-10-16-v4` |
| Held-out seeds | 1300-1329, never generated before this run. The harness refuses spent seeds (v1 1000-1029, v2 1100-1129, v3 1200-1229), development seeds 0-9 and P8's reserved 7000-8059. |
| Rule | verbatim in `freeze.json` (`inputs.rule`), unchanged since v2. `decide()`, `COST_RATIO` 1.25 and `ALPHA` 0.05 are unchanged. |
| Code | the import closure of the harness and the isolated worker, all of `greg/cognition`, the extras and the dependency versions, each hashed in `freeze.json` |
| Run | once, in a clean detached worktree at the commit that adds this file, pinned to one CPU core, on a quiet machine. A crash is recorded, never retried. |
| Arms, statistics, canonical path | as in v3: the candidate's outputs pass through its independent verifier (a refuted output is scored wrong); the declared baseline and strongest competitor; paired one-sided exact sign tests; median wall-clock latency; one held-out instance per genome through `greg.cognition.cortex.reason` in an evaluation-only registry view |
| Diagnostics, not decision inputs | new since v3 (`80d6fc1`): thread CPU time per call and median CPU seconds per arm, plus the host load at the start and end. The decision reads wall-clock medians only, as before. |

## Families (3): every genome whose version changed after its last verdict

| Family | Last verdict (version) | Now | What changed |
|---|---|---|---|
| `grid_dijkstra` | EXPERIMENTAL, v3 (1.0.0): ties on all 30, 1.22x its baseline's speed, short of 1.25x | 1.1.0 | Same SciPy Dijkstra, same potential certificate and same verifier. The graph is now built as a fixed-degree CSR from whole-grid slices, with a faster input check. Distances and certificates are guaranteed unchanged; routes were identical on every grid tested (an observation, not a guarantee). |
| `flow_reinforce_greedy` | SUPERSEDED, v3 (1.0.1) | 1.0.2 | Refuses parallel edges in capacity expansion (verifier lane, 2026-10-15 review) |
| `flow_capacity_plan` | COMPOSITION_ONLY, v3 (1.0.2) | 1.0.3 | Refuses parallel edges in capacity expansion (same change) |

## Design knowledge, disclosed

- **`grid_dijkstra` 1.1.0, review seeds only.** It was profiled and measured on review seeds 3000-3099 by its builder and 3300-3399 by its independent critic (`design/grid-genome`, merged at `5719dc7`).
  - Under heavy load, the wall-clock ratio over A* read 2.6-7.6x (the builder's runs, load average 5.6-9.5).
  - The CPU-clock ratio read 2.16-2.41x (the critic's runs, load average 7.8-9.3). On that clock, 1.0.0 read 1.33-1.51x, and v3's 1.22x was a plausible draw.
  - On uniform-cost obstacle grids, 1.1.0 has no latency edge over A* (0.96-1.24x). The expected pass rests on the open-weighted and walls-and-mud subregions.
  - **Prediction, not part of the rule:** DEFAULT_FOR_GEOMETRY. The wall-clock ratio is expected near 1.9-2.4x on a quiet machine; a ratio below 1.25x would make it EXPERIMENTAL again.
- **The flow genomes:** no new measurement was made. Their outputs are unchanged on inputs without parallel edges, which the admission generators do not produce, so v3's statuses are expected to replicate.

## What the outcome changes, and what it cannot

- A DEFAULT or NICHE verdict makes a genome routable at its exact version. It does not attach it: attaching is the founder's decision.
- A SUPERSEDED, EXPERIMENTAL or REJECTED verdict excludes the genome from routing until a later re-admission.
- The evidence index is rebuilt from `results.json` after the run. The tests that pin `grid_dijkstra`'s v3 state are updated in the same commit.
- Nothing is re-run, re-scored or re-labelled. The README is generated from `results.json` by script, and negative verdicts are reported as prominently as positive ones.
