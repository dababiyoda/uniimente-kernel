# Genome admission v5: DRAFT pre-registration (not frozen)

**Status: DRAFT for the session owner.** Nothing here is frozen. No `freeze.json` exists, and no held-out instance has
been generated. To freeze, the owner copies this file to `docs/evidence/greg-genome-admission/<run-id>/PREREGISTRATION.md`
and runs `admission --freeze <run-id> --only <families> --heldout-start 1400` at a commit that contains both. The run
then happens exactly once.

## Proposed fixed items

| Item | Proposed value |
|---|---|
| Held-out seeds | 1400-1429 |
| Rule | `RULE` verbatim, unchanged; `decide()`, `COST_RATIO` 1.25 and `ALPHA` 0.05 are also unchanged |
| Code | the harness's import closure, all of `greg/cognition`, the extras and the dependency versions, hashed in `freeze.json` |
| Run | once, in a clean detached worktree, pinned to one core, on a quiet machine (the dev runs read a load of about 5; see the README) |

The checks behind seeds 1400-1429, made 2026-10-21 on branch `lane/l3-absent`:

- No `docs/evidence/greg-genome-admission/*/freeze.json` uses them. Existing held-out seeds span 1000-1329.
- #179's `spent_seeds()` sources (read at `d0c2733e`) do not include them. Its genome freezes are as above, and its
  `cortex/evaluation/genome_admission/freeze-ops-v*.json` declares 5001-5040; the v1/v2 operation freezes declare
  1001-1040 and 2001-2040.
- They are outside `DEV_SEEDS` (0-9), `P8_RESERVED` (7000-9199) and #179's recipe-lift reservation (6501-6840).
- A seed-context grep over every local branch found no declaration of 1400-1429.
- The harness's own `spent_seeds` check refuses spent seeds at freeze time and should be relied on.

## Families (6), all new at 1.0.0

| Family | Layer | Baseline | Competitor | Dev-only expectation (not part of the rule) |
|---|---|---|---|---|
| `maxsat_cpsat` | 3 | weighted polarity plus single-variable flips | Z3 Optimize (MaxRes) | NICHE (exact, but slower than Z3; Z3 returned 2 non-optimal models on 10 dev seeds) |
| `binpack_cpsat` | 3 | first-fit decreasing | HiGHS on the assignment model | EXPERIMENTAL or DEFAULT (an abstention under load decided it on dev) |
| `reconcile_qp` | 3 | weighted projection, clipped | SciPy SLSQP | SUPERSEDED (ties SLSQP on every seed; SLSQP is faster) |
| `community_louvain` | 3 | label propagation | CNM greedy modularity | DEFAULT |
| `blackbox_multistart_lbfgsb` | 3 | single L-BFGS-B start | differential evolution | EXPERIMENTAL (DE stronger on multimodal objectives) |
| `crowd_weighted_vote` | 2 | plurality vote | Dawid-Skene EM | DEFAULT |

## Design knowledge, disclosed

- Each genome was built and inspected on dev seeds 0-9. Bin packing and reconciliation were also inspected on review
  seeds 9300-9339. The changes made on dev seeds were:
  - the bin-packing capacities, cut from {100, 150, 1000} to {100, 120, 150};
  - the bin-packing solver, rewritten from minimisation to per-count feasibility with a cardinality cut;
  - the cardinality cut, also given to the HiGHS competitor;
  - the reconciliation flow-network generator, rewritten after the first one could loop forever.
- No parameter of the multistart or Louvain genomes was tuned after their dev results were seen.
- Ground truth for MaxSAT comes from HiGHS. HiGHS is also the bin-packing competitor, and the bin-packing verifier
  uses it only when the L2 bound does not close.

## What the outcome changes, and what it cannot

- A DEFAULT or NICHE verdict makes a genome routable at version 1.0.0. It does not attach it.
- SUPERSEDED, EXPERIMENTAL and REJECTED verdicts exclude a genome from routing.
- Negative verdicts are reported as prominently as positive ones.
