# Genome admission v7: pre-registration (2026-10-21)

**Status:** pre-registered. This file is committed before `freeze.json`, and both are committed before any held-out
instance is generated. The run refuses to report if any frozen input differs.

It merges three lane drafts, which stay unchanged as lineage. Each draft discloses everything its lane learned on
development seeds 0-9, including every change made after a dev result was seen, and that disclosure is part of this
pre-registration:
- `docs/evidence/greg-genome-admission/2026-10-21-v7-draft-search.md`: `search_ida_star`, `search_beam`, `search_mcts`
- `docs/evidence/greg-genome-admission/2026-10-21-v7-draft-evo.md`: `evo_ga_factored`, `evo_map_elites`, `graph_betweenness_topk`
- `docs/evidence/greg-genome-admission/2026-10-21-v7-draft-formal.md`: `formal_property_search`, `basal_hopfield`, `develop_ca_repair`

All three drafts proposed the same seeds, so there is one freeze over all nine families.

## What is fixed before the run

| Item | Value |
|---|---|
| Run id | `2026-10-21-v7` |
| Held-out seeds | 1600-1629 (`--heldout-start 1600`) |
| Families | the 9 listed below, all new at 1.0.0 |
| Rule | `RULE` verbatim, unchanged since v2; `decide()`, `COST_RATIO` 1.25 and `ALPHA` 0.05 are unchanged |
| Code | the harness's import closure, all of `greg/cognition`, the extras and the dependency versions, each hashed in `freeze.json` |
| Arms and statistics | as in v4-v6 |
| Run | once, in a clean detached worktree at the commit that adds `freeze.json`, pinned to one core. A crash is recorded, never retried |
| Machine | starts only after the design lanes have finished and the 1-minute load is below 1.5; start and end load are recorded as diagnostics |

**Arms and statistics, as in v4-v6:**
- every candidate output passes through its own independent verifier, and a refuted output is scored wrong;
- the declared baseline and the strongest competitor each lane named;
- paired one-sided exact sign tests;
- median wall-clock latency, with CPU time as a diagnostic;
- one held-out instance per genome through `greg.cognition.cortex.reason`, in an evaluation-only registry view.

**Why 1600-1629 are fresh:**
- No genome-admission freeze uses them. Admission held-out spans already used: 1000-1029, 1100-1129, 1200-1229, 1300-1329, 1400-1429 and 1500-1529.
- No #179 freeze uses them (1001-1040, 2001-2040, 3001-3040, 5001-5040 and 6501-6840 are #179's).
- They are not P8-reserved (7000-9199) and not in a declared development range (9300-9339, 9400-9439).
- The exposure ledger records no exposure of 1600-1629 for any generator.
- All nine generators are new: before this freeze, the ledger shows only their development seeds 0-9.
- The harness's spent-seed and reused-instance checks run again at freeze time.

## Families (9)

| Family | Layer | Coverage item closed if admitted | Baseline | Competitor | Dev-only expectation (not part of the rule) |
|---|---|---|---|---|---|
| `search_ida_star` | 3 | L3.search.iterative_deepening | breadth-first search, same memory budget | A* with the same heuristic, same memory budget | DEFAULT, resting on the declared memory budget |
| `search_beam` | 3 | L3.search.beam | NEH | CP-SAT warm-started from NEH, 2 s | EXPERIMENTAL; the competitor rarely improves on NEH, so the test is weak |
| `search_mcts` | 3 | L3.search.mcts | flat Monte Carlo, same budget | alpha-beta with resistance evaluation | EXPERIMENTAL; UCT showed no edge over flat Monte Carlo |
| `evo_ga_factored` | 3 | L3.evo.ga | random-restart hill climbing | CP-SAT on the exact factor model | EXPERIMENTAL; loses random NK to hill climbing; trap kinds were added after a prototype |
| `evo_map_elites` | 3 | L3.evo.quality_diversity | random search | differential evolution on quality alone, all evaluations archived | DEFAULT, against a competitor that is weak by construction |
| `graph_betweenness_topk` | 3 | L3.graph.centrality | the k highest-degree nodes | NetworkX exact betweenness | DEFAULT on latency alone (ties NetworkX) |
| `formal_property_search` | 3 | L3.formal.property_based | uniform random inputs, same budget | Z3 symbolic search | EXPERIMENTAL or SUPERSEDED (Z3 proves the decoys clean) |
| `basal_hopfield` | 1 | L1.eval.associative_networks | no recall (the cue) | exact Hamming nearest neighbour | EXPERIMENTAL or SUPERSEDED (nearest neighbour is the accuracy ceiling) |
| `develop_ca_repair` | 4 | L4.now.cellular_automata | no repair | Z3 global entailment | DEFAULT on cost only (ties Z3); any difference could only be a loss |

**Expected wall time:** the search lane measured up to about 60 s per seed to build Hex positions, and up to 10 s per
alpha-beta instance. The run may take an hour; slowness is recorded, never a reason to stop and retry.

## What the outcome changes, and what it cannot

- A DEFAULT or NICHE verdict makes a genome routable at version 1.0.0. It attaches nothing; attaching is the founder's decision.
- SUPERSEDED, EXPERIMENTAL and REJECTED verdicts exclude a genome from routing. They are reported as prominently as positive ones, and the coverage item stays BENCHMARKED, not ADMITTED.
- Every instance is mathematical or simulated. A verdict says nothing about a natural workload.
