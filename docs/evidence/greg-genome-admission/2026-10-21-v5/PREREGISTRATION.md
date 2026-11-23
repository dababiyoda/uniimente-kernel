# Genome admission v5: pre-registration (2026-10-21)

**Status:** pre-registered. This file is committed before `freeze.json`, and both are committed before any held-out
instance is generated. The run refuses to report if any frozen input differs.

It merges three lane drafts, kept unchanged as lineage. The drafts disclose what each lane learned on development
data; that disclosure is part of this pre-registration.
- `docs/evidence/greg-genome-l3-absent-2026-10-21/ADMISSION-V5-PREREGISTRATION-DRAFT.md`
- `docs/evidence/greg-genome-admission/2026-10-21-v5-draft-nodecut.md`
- `docs/evidence/greg-genome-admission/2026-10-21-v5-draft-l124.md`

Two drafts proposed the same seeds, so there is one freeze over every family.

## What is fixed before the run

| Item | Value |
|---|---|
| Run id | `2026-10-21-v5` |
| Held-out seeds | 1400-1429 (`--heldout-start 1400`) |
| Families | the 11 listed below, all new at 1.0.0 |
| Rule | `RULE` verbatim, unchanged since v2; `decide()`, `COST_RATIO` 1.25 and `ALPHA` 0.05 are unchanged |
| Code | the harness's import closure, all of `greg/cognition`, the extras and the dependency versions, each hashed in `freeze.json` |
| Arms and statistics | as in v4 |
| Run | once, in a clean detached worktree at the commit that adds `freeze.json`, pinned to one core. A crash is recorded, never retried |
| Machine | the run starts only after the parallel design lanes have finished and the 1-minute load is below 1.5. Start and end load are recorded as diagnostics |

**Arms and statistics, as in v4:**
- every candidate output passes through its own independent verifier, and a refuted output is scored wrong;
- the declared baseline and the strongest competitor;
- paired one-sided exact sign tests;
- median wall-clock latency, with CPU time as a diagnostic;
- one held-out instance per genome through `greg.cognition.cortex.reason`, in an evaluation-only registry view.

**Why 1400-1429 are fresh:**
- No genome-admission freeze uses them. The spans already used are 1000-1029, 1100-1129, 1200-1229 and 1300-1329.
- No #179 operation freeze uses them. Those are 1001-1040, 2001-2040 and 5001-5040, read at `d0c2733e`.
- They are not P8-reserved (7000-9199) and not in #179's recipe-lift reservation (6501-6840).
- They are not in the declared development ranges 9300-9339 and 9400-9439.
- The exposure ledger (`docs/evidence/greg-data-exposure-ledger.json`) records no exposure of them.
- The harness's spent-seed and reused-instance checks run again at freeze time.

## Families (11)

| Family | Layer | Baseline | Competitor | Development-only expectation |
|---|---|---|---|---|
| `maxsat_cpsat` | 3 | weighted polarity + single flips | Z3 Optimize (MaxRes) | NICHE: exact, slower than Z3, which returned 2 wrong optima on dev |
| `binpack_cpsat` | 3 | first-fit decreasing | HiGHS assignment model | EXPERIMENTAL or DEFAULT |
| `reconcile_qp` | 3 | weighted projection, clipped | SciPy SLSQP | SUPERSEDED |
| `community_louvain` | 3 | label propagation | CNM greedy modularity | DEFAULT |
| `blackbox_multistart_lbfgsb` | 3 | single L-BFGS-B start | differential evolution | EXPERIMENTAL |
| `crowd_weighted_vote` | 2 | plurality | Dawid-Skene EM | DEFAULT |
| `graph_node_cut_exact` | 3 | betweenness greedy | `flow_maxflow` on the node-split graph | DEFAULT: any win beyond `flow_maxflow`'s bounds is bounds coverage, reported by subregion |
| `basal_token_bucket` | 1 | plain token bucket | online bid-price | EXPERIMENTAL |
| `basal_nlms` | 1 | running mean | RLS (forgetting 0.995) | DEFAULT on latency |
| `collective_auction` | 2 | greedy by value | `linear_sum_assignment` | SUPERSEDED |
| `develop_diffusion` | 4 | nearest seed | Louvain + seed vote | EXPERIMENTAL or worse |

These expectations are design knowledge, not part of the rule.

**Not in this run:** the node-cut ILP is a second competitor, and the harness supports one. It stays a
development-only measurement and is not a v5 claim.

## What the outcome changes, and what it cannot

- A DEFAULT or NICHE verdict makes a genome routable at 1.0.0. It does not attach it; attaching is the founder's
  decision (`docs/collaboration/FOUNDER-DECISIONS-2026-10-21.md`, D3).
- SUPERSEDED, EXPERIMENTAL and REJECTED verdicts exclude a genome from routing.
- The README is generated from `results.json`. Negative verdicts are reported as prominently as positive ones.
- The evidence index is rebuilt from `results.json` in the same commit.
