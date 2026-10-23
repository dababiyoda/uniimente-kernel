# Antifragility v3b: result

**Verdict by the frozen rule: NO_GAIN** (rule 2: no cell preference fired during the 120 stress missions).

- **Frozen** at `07b9f128` (workload `sha256:89d592a8…`), on a tree containing `78da0332`.
- **Run** once, from a clean detached worktree on one pinned core: 2026-10-22T08:57:42Z to 09:50:49Z, exit 0.
- **Files:** `result.json`, `run.log`.
- **Stopping rule:** v3b is the last experiment in this line. There will be no v3c, no further key and no rerun.

## Stress (120 HIGH missions, seeds 6100-6219)

| Cell (d11-30) | Pairs | Multistart only | Swarm only |
|---|---:|---:|---:|
| Rosenbrock | 7 | 3 | 0 |
| Griewank | 12 | 2 | 0 |
| Sphere | 11 | 2 | 0 |
| Rastrigin | 15 | 2 | 0 |
| Ackley | 16 | 0 | 0 |

- **Firing:** no cell reached the five discordant pairs the preference needs, so it never fired. The design's power (0.935) assumed v3's discordance rates. Here most pairs were concordant, and Rosenbrock, which was 6-0 in v3, gave 3-0.
- **Missions:** 80 of 120 stress missions failed.
- **Shadows:** 119 trials, 1,190,000 evaluations, 27.9 s.

## Holdout (200 instances, seeds 6300-6319, 20 per cell)

LOW passes are 88 in every arm except B2, which has 99, so no arm regressed on LOW.

| Arm | Total | HIGH Ackley | HIGH Griewank | HIGH Rastrigin | HIGH Rosenbrock | HIGH Sphere |
|---|---:|---:|---:|---:|---:|---:|
| PRE | 131 | 7 | 9 | 9 | 7 | 11 |
| LEARN | 131 | 7 | 9 | 9 | 7 | 11 |
| CONTROL | 131 | 7 | 9 | 9 | 7 | 11 |
| S (shuffled) | 131 | 7 | 9 | 9 | 7 | 11 |
| A (v3's coarse key) | 156 | 0 | 20 | 8 | 20 | 20 |
| B1 (best of 4 swarm runs) | 174 | 19 | 18 | 17 | 14 | 18 |
| B2 (best of both) | 180 | 7 | 20 | 14 | 20 | 20 |

- **LEARN, PRE, CONTROL and S** are identical on every instance (0-0 discordant), so the learned routing changed no answer.
- **LEARN's cost:** it still spent 1,000,000 shadow evaluations on the holdout, against CONTROL's none.

## A, the coarse key (reported, not ruled)

On the same stress journal, v3's dimension-only key merges the per-objective pairs: 9-0 discordant, which fired. A routed every HIGH instance to multistart.

- **Against LEARN:** 38-13 (one-sided sign test p = 0.0003).
- **On Ackley:** it fell from 7 to 0. Under rule 5 it could not have been GAIN, because a cell regresses.
- **Against B1:** it loses 11-29 (p = 0.003).

So the finer key split the evidence below the firing threshold in every cell. The coarse key had enough evidence to fire, but it routed Ackley wrong.

## B1, compute-matched restarts

The incumbent swarm run four times (k = 4 by the frozen formula), each run within the accepted budget, keeping the best answer.

- **Against LEARN:** 174 against 131, 43-0.
- **Against B2:** B2 is ahead 180-174 with a 2× budget, 22-16 discordant (p = 0.21), which is not significant.

On this data, spending the shadow budget on restarts of the incumbent beats learning which method to route to, under either key.

## What this settles

- **The §14 learning mechanism:** v3 and v3b are both NO_GAIN. It is integrated, inert by default and tested (27 unit and hook tests; 12 of 12 mutants caught). On these objectives its routing gain has not been shown.
- **The comparison that wins:** compute-matched restarts. Any future proposal for condition-specific routing on this geometry must beat B1, not CONTROL.
- **Production:** `KEY` stays `"dimension"`, and the mechanism stays off unless the founder attaches it.
- **Authority:** none created. Nothing was attached, spent, published or merged. VEPMC: 0.
