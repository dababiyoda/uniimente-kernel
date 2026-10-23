# Genome admission v7 (2026-10-21): 5 DEFAULT, 2 EXPERIMENTAL, 2 SUPERSEDED

- **Pre-registration:** [`PREREGISTRATION.md`](PREREGISTRATION.md), committed in `b1ee3f97`. It merges three lane drafts, kept as lineage: `../2026-10-21-v7-draft-search.md`, `../2026-10-21-v7-draft-evo.md` and `../2026-10-21-v7-draft-formal.md`.
- **Freeze:** [`freeze.json`](freeze.json), committed in `568c4b7b` before any held-out instance was generated. The exposure ledger that cites it follows in `98a2ab0c`.
- **Run:** once, from a clean detached worktree of `568c4b7b`, under `taskset -c 1`, load 0.85 to 1.07, 29 minutes wall. Outputs: [`results.json`](results.json) and [`run.log`](run.log).
- **Rule:** `RULE` verbatim, unchanged. Held-out seeds 1600-1629.

## Generated from results.json (`scripts/admission_readme.py`)

- **Run:** source commit `568c4b7b`, source dirty [], freeze `sha256:5b29d465d6a6fd1e…`, finished 2026-10-21T23:52:34.532316+00:00.
- **Host load:** start {'1m': 0.85, '5m': 0.97, '15m': 0.99, 'runnable': 1, 'entities': 107}, end {'1m': 1.07, '5m': 1.02, '15m': 1.04, 'runnable': 1, 'entities': 106} (diagnostic only).

| Family | Layer | Version | Status | Candidate correct/wrong/abstain | vs baseline W-L-T (p better) | vs competitor W-L-T (p better / p worse) | Median s (candidate / baseline / competitor) | Canonical path |
|---|---|---|---|---|---|---|---|---|
| `basal_hopfield` | 1 | 1.0.0 | **SUPERSEDED** | 15/0/15 | 15-0-15 (3.1e-05) | 0-15-15 (1.0 / 3.1e-05) | 0.000749 / 0.000107 / 0.000172 | STRUCTURALLY_VERIFIED |
| `develop_ca_repair` | 4 | 1.0.0 | **DEFAULT_FOR_GEOMETRY** | 30/0/0 | 30-0-0 (0.0) | 0-2-28 (1.0 / 0.25) | 0.001918 / 0.000109 / 0.084842 | STRUCTURALLY_VERIFIED |
| `evo_ga_factored` | 3 | 1.0.0 | **EXPERIMENTAL** | 30/0/0 | 19-10-1 (0.068023) | 15-15-0 (0.572232 / 0.572232) | 0.034291 / 0.044541 / 0.690507 | STRUCTURALLY_VERIFIED |
| `evo_map_elites` | 3 | 1.0.0 | **DEFAULT_FOR_GEOMETRY** | 30/0/0 | 30-0-0 (0.0) | 30-0-0 (0.0 / 1.0) | 0.054985 / 0.026932 / 0.146263 | STRUCTURALLY_VERIFIED |
| `formal_property_search` | 3 | 1.0.0 | **SUPERSEDED** | 23/0/7 | 13-0-17 (0.000122) | 0-7-23 (1.0 / 0.007812) | 0.000813 / 0.006361 / 0.009921 | STRUCTURALLY_VERIFIED |
| `graph_betweenness_topk` | 3 | 1.0.0 | **DEFAULT_FOR_GEOMETRY** | 30/0/0 | 28-0-2 (0.0) | 0-0-30 (1.0 / 1.0) | 0.043396 / 0.001081 / 0.179274 | STRUCTURALLY_VERIFIED |
| `search_beam` | 3 | 1.0.0 | **DEFAULT_FOR_GEOMETRY** | 30/0/0 | 18-0-12 (4e-06) | 14-3-13 (0.006363 / 0.998825) | 0.118442 / 0.003947 / 2.031024 | STRUCTURALLY_VERIFIED |
| `search_ida_star` | 3 | 1.0.0 | **DEFAULT_FOR_GEOMETRY** | 30/0/0 | 23-0-7 (0.0) | 2-0-28 (0.25 / 1.0) | 0.011964 / 0.087872 / 0.020286 | STRUCTURALLY_VERIFIED |
| `search_mcts` | 3 | 1.0.0 | **EXPERIMENTAL** | 29/1/0 | 1-1-28 (0.75) | 12-1-17 (0.001709 / 0.999878) | 0.066907 / 0.037985 / 6.55856 | STRUCTURALLY_VERIFIED |

`basal_hopfield` by subregion: low_load_biased (n=10): vs baseline 8-0-2, vs competitor 0-2-8; low_load_random (n=5): vs baseline 5-0-0, vs competitor 0-0-5; over_capacity_biased (n=11): vs baseline 1-0-10, vs competitor 0-10-1; over_capacity_random (n=4): vs baseline 1-0-3, vs competitor 0-3-1.

`develop_ca_repair` by subregion: first_row_damaged (n=17): vs baseline 17-0-0, vs competitor 0-2-15; first_row_intact (n=13): vs baseline 13-0-0, vs competitor 0-0-13.

`evo_ga_factored` by subregion: loose_linkage_deceptive (n=7): vs baseline 4-3-0, vs competitor 0-7-0; loose_linkage_rugged (n=8): vs baseline 4-4-0, vs competitor 8-0-0; tight_linkage_deceptive (n=8): vs baseline 6-1-1, vs competitor 0-8-0; tight_linkage_rugged (n=7): vs baseline 5-2-0, vs competitor 7-0-0.

`evo_map_elites` by subregion: high_dim_coarse (n=3): vs baseline 3-0-0, vs competitor 3-0-0; high_dim_fine (n=14): vs baseline 14-0-0, vs competitor 14-0-0; low_dim_coarse (n=4): vs baseline 4-0-0, vs competitor 4-0-0; low_dim_fine (n=9): vs baseline 9-0-0, vs competitor 9-0-0.

`formal_property_search` by subregion: equality_guard (n=12): vs baseline 7-0-5, vs competitor 0-1-11; inequality_guard (n=12): vs baseline 6-0-6, vs competitor 0-1-11; no_added_guard (n=6): vs baseline 0-0-6, vs competitor 0-5-1.

`graph_betweenness_topk` by subregion: flat_degree (n=22): vs baseline 22-0-0, vs competitor 0-0-22; hub_skewed (n=8): vs baseline 6-0-2, vs competitor 0-0-8.

`search_beam` by subregion: large (50 jobs) (n=9): vs baseline 5-0-4, vs competitor 4-1-4; medium (30 jobs) (n=5): vs baseline 2-0-3, vs competitor 2-0-3; small (<= 20 jobs) (n=16): vs baseline 11-0-5, vs competitor 8-2-6.

`search_ida_star` by subregion: 3x3 (n=12): vs baseline 5-0-7, vs competitor 0-0-12; 4x4 (n=18): vs baseline 18-0-0, vs competitor 2-0-16.

`search_mcts` by subregion: 6x6 (n=15): vs baseline 1-0-14, vs competitor 10-0-5; 7x7 (n=15): vs baseline 0-1-14, vs competitor 2-1-12.

## Reading

**Admitted (DEFAULT_FOR_GEOMETRY), each with the limit that matters:**

- **`search_ida_star`: optimal sliding-puzzle plans under a declared memory budget.**
  - It beats breadth-first search 23-0 and A\* 2-0-28.
  - Both wins are 4x4 instances where A\* ran out of the shared 100,000-position budget. Without that budget A\* would tie and be faster.
- **`search_beam`: flow-shop sequencing.**
  - It beats NEH 18-0.
  - It beats the CP-SAT competitor (warm-started from NEH, 2 s) 14-3, at 0.12 s against 2.0 s.
  - The quality gains are small: mean bound/makespan 0.864 against 0.861 for CP-SAT and 0.858 for NEH.
  - The published best method for this problem, Iterated Greedy, is not installed and was not compared. This verdict is DEFAULT against the competitor that was measured, not against the state of the art.
- **`evo_map_elites`: a quality-diversity archive.**
  - It beats random search and differential evolution 30-0 each.
  - The competitor is weak by construction: it optimises quality alone, then archives every evaluation. A per-cell optimiser was not built.
- **`graph_betweenness_topk`: exact top-k betweenness.**
  - It ties NetworkX's exact answer on 30 of 30, at 0.043 s against 0.179 s.
  - The verdict rests on latency, under the rule's latency clause.
- **`develop_ca_repair`: local-rule regeneration of a CA pattern.**
  - It restores only cells forced by the local rule and never guesses.
  - It beats no repair 30-0 and loses 0-2-28 to Z3 global entailment. That is not significant (p = 0.25), and it runs at 0.002 s against 0.085 s.
  - Both losses are items whose first row is damaged, where whole-pattern inference forces cells local propagation cannot. The declaration predicted that any difference could only be a loss. The verdict is DEFAULT on cost, and the two losses are a measured limit.

**Not admitted:**

- **`evo_ga_factored`: EXPERIMENTAL.**
  - It beats hill climbing 19-10, which is not significant (p = 0.068). Against CP-SAT it is 15-15.
  - The subregions split cleanly. On rugged NK landscapes the GA beats time-limited CP-SAT 15-0, and CP-SAT abstained on 5. On deceptive traps CP-SAT solves exactly and wins 15-0.
  - That is a plausible niche: rugged landscapes too large for exact search in its time limit. It is not admitted, because the rule's baseline test failed.
- **`search_mcts`: EXPERIMENTAL.**
  - UCT ties flat Monte Carlo on 28 of 30, with 1-1 on the rest. It beats alpha-beta 12-1, at 0.067 s against 6.6 s.
  - The candidate gave 1 wrong answer (a losing move), as did flat Monte Carlo; alpha-beta gave 13.
  - UCT adds nothing over flat Monte Carlo at this budget and position size.
- **`formal_property_search`: SUPERSEDED.**
  - It beats uniform random testing 13-0 and finds 23 of 30 counterexamples.
  - Z3 finds all 30, proves the decoys clean, and wins 7-0.
  - Where a symbolic encoding exists, symbolic search dominates. Random property testing keeps its place only where it does not, which this benchmark does not test.
- **`basal_hopfield`: SUPERSEDED.**
  - It recalls exactly on 15 and abstains on 15 (no false recall).
  - Exact nearest neighbour is right on 30 of 30 and faster.
  - Above the network's capacity, it abstains instead of recalling. The bounded-memory niche is not measured by this request format.

**What the outcome changes:**
- Five genomes become routable at 1.0.0. None is attached; attaching is the founder's decision.
- The coverage items for IDA\*, beam search, quality-diversity, centrality and CA regeneration reach ADMITTED.
- MCTS, GA, property-based testing and associative memory reach BENCHMARKED.

**What it does not show:** every instance is mathematical or simulated. Thirty items per family make subregion counts descriptive only.
