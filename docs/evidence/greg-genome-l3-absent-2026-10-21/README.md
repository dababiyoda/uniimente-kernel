# Layer 3 ABSENT families, batch D, and the L2 one-step crowd vote (2026-10-21)

**DEVELOPMENT ONLY.** Every number here comes from development seeds 0-9 (`admission --dev`), plus checks on this lane's
declared review range 9300-9399 in the unit tests. These numbers are **not admission evidence**. The genomes were
built and inspected on these same seeds. Nothing here is admitted or attached. Each family is registered **withheld**
(`VERIFIED`), and attaching one is the founder's decision.

- Branch: `lane/l3-absent`, based on `09555108`.
- Code commit: `9fe1c86e`.
- Dev outputs: `dev/*.json`, verbatim from `python -m greg.cognition.genomes.admission --dev FAMILY`. Each run was
  pinned with `taskset -c 0`.
- Host load: the 1-minute load average read 4.75-5.15 throughout. The host was loaded, so wall-clock latencies are
  inflated and may be inflated unevenly across arms. `diagnostics.median_cpu_seconds` in each file gives the CPU clock.

## What was built

The 2026-10-21 coverage record lists these Layer 3 requirements as ABSENT: SAT, packing, convex optimisation and
community / topology analysis. It names multistart L-BFGS-B as an acquisition target (build item B08). The
coordinator's scope addition added two acquisition targets handed over by #179: the one-step weighted crowd vote (B07)
and multistart L-BFGS-B.

Every family:

- runs on an installed engine;
- has an independent verifier that recomputes the answer or checks a certificate, never trusting the solver's claim;
- passes the library-wide test that corrupts each single leaf of an answer, so a corrupted answer is refuted;
- is reachable through `greg.cognition.cortex.reason` and the Competency Compiler by its inputs (tested with an
  in-memory attach only).

| Family (operation) | Layer | Engine | Independent verifier | Baseline | Competitor | GREG need |
|---|---|---|---|---|---|---|
| `maxsat_cpsat` (`weighted_maxsat`) | 3 | OR-Tools CP-SAT | recomputes the violated clauses and their weight; Z3 proves that no assignment satisfying the hard clauses violates less weight (pseudo-Boolean bound), or that the hard clauses are UNSAT; the assignment must match the certificate's witness digest | weighted polarity plus single-variable flips | Z3 Optimize (MaxRes) | reconciling claims from sources of known reliability under hard rules |
| `binpack_cpsat` (`bin_packing_min_bins`) | 3 | first-fit decreasing (FFD), then CP-SAT feasibility for each bin count from the volume bound upward | checks the partition, loads and canonical order; an independent Martello-Toth L2 bound, or SciPy HiGHS proving that one bin fewer is infeasible | first-fit decreasing | HiGHS on the assignment model, with the same symmetry breaking and cardinality cut | how many workers or containers to provision |
| `reconcile_qp` (`reconcile_measurements`) | 3 | HiGHS LP start, then a primal active-set method on exact KKT faces (NumPy) | KKT certificate: balances, non-negativity, multiplier signs, complementarity, stationarity and the objective; a Farkas vector for claimed infeasibility | textbook weighted projection, with negatives clipped to zero | SciPy SLSQP | reconciling inconsistent numeric estimates against known totals and balances |
| `community_louvain` (`detect_communities`) | 3 | networkx Louvain, best of 5 seeds, plus a node-move polish | recomputes the partition and the modularity with its own formula; no single-node move may improve the result (verifier code separate from the polish) | label propagation | Clauset-Newman-Moore greedy modularity | breaking a dependency or collaboration graph into modules |
| `blackbox_multistart_lbfgsb` (`continuous_minimize`) | 3 | multistart SciPy L-BFGS-B under a strict evaluation budget | re-evaluates the objective with independent vectorised NumPy; checks the box and the budget; never claims global optimality | one L-BFGS-B start from the centre of the box | differential evolution at the same budget (#179's `blackbox`) | tuning a declared continuous objective |
| `crowd_weighted_vote` (`weighted_vote_labels`) | 2 | one-step Nitzan-Paroush weighted vote | recomputes every weight and label over a worker-major index | plurality vote | Dawid-Skene EM, ported from #179 `repertoire.crowd_label` (d0c2733e) | combining reviewers or sources of unequal reliability |

How each family's ground truth is computed, independent of every arm:

- **MaxSAT:** SciPy HiGHS on the 0/1 program, a third engine.
- **Bin packing:** the optimum is planted. Each instance is built from k full bins, or from bins whose total slack is
  less than one bin, so the optimum is k.
- **Reconciliation:** exhaustive enumeration of every set of zero bounds, for up to 12 values.
- **Communities:** the planted block partition. Quality is the recomputed modularity.
- **Black-box:** the known minimum of each declared shifted objective.
- **Crowd:** the simulated true labels.

## Development results (seeds 0-9; not evidence)

Wins, losses and ties are on the genome's native quality. Latency is the median wall-clock time on the loaded host.
"Would be" is what the frozen rule (`RULE`, unchanged) gives on these ten seeds. It is not an admission verdict.

| Family | vs baseline (W-L-T) | vs competitor (W-L-T) | Wrong answers: cand / base / comp | Median latency: cand / comp | Would be |
|---|---|---|---|---|---|
| `maxsat_cpsat` | 9-0-1 | 3-0-7 | 0 / 7 (2 abstain) / 2 (1 abstain) | 173 ms / 96 ms | NICHE_CAPABILITY |
| `binpack_cpsat` | 6-1-3 | 1-1-8 | 0 (1 abstain) / 7 / 2 | 180 ms / 898 ms | EXPERIMENTAL |
| `reconcile_qp` | 9-0-1 | 0-0-10 | 0 / 9 / 0 | 6.8 ms / 1.2 ms | SUPERSEDED |
| `community_louvain` | 10-0-0 | 10-0-0 | 0 / 0 / 0 | 76 ms / 57 ms | DEFAULT_FOR_GEOMETRY |
| `blackbox_multistart_lbfgsb` | 4-0-6 | 1-4-5 | 0 / 0 / 0 | 342 ms / 469 ms | EXPERIMENTAL |
| `crowd_weighted_vote` | 10-0-0 | 9-1-0 | 0 / 0 / 0 | 6.6 ms / 198 ms | DEFAULT_FOR_GEOMETRY |

Each row's reading, negative findings included:

- **`maxsat_cpsat`: exact on all ten seeds.**
  - Z3 Optimize returned non-optimal models while reporting `sat` on dev seeds 4 and 8 (1495 vs the optimum 1373, and
    1147 vs 877). Both are claims-and-rules instances with complementary unit soft clauses.
  - Merging duplicate soft clauses did not fix it. Z3's `wmax` engine gave the optimum on both seeds.
  - The candidate's verifier refutes Z3's model (`test_z3_optimize_competitor_failure_is_caught_by_the_verifier_on_dev_seed_4`).
  - The candidate is 1.8x slower than Z3 on the median, so the latency rule makes it NICHE, not DEFAULT.
- **`binpack_cpsat`: no measured edge over FFD on these seeds.**
  - One instance hit the 5 s budget and abstained (UNKNOWN). Most likely it was seed 4, which took 3.7 s unloaded.
  - CP-SAT handles planted perfect packings with capacity 1000 poorly. That first generator variant timed out on 3 of
    10 seeds. The benchmark now uses capacities of 100-150. This is a disclosed design change made on dev seeds, and
    the known failure modes record it.
  - An arc-flow model was also tried, on both CP-SAT and HiGHS. It was slower, and it was not kept.
  - On review seeds 9300-9339, the candidate answered all 40 and verified all 40. FFD was wrong on 27 of them, and
    HiGHS on 1.
- **`reconcile_qp`: SUPERSEDED.**
  - SciPy SLSQP ties it on every seed and is 5.7x faster.
  - What the rule does not count is that the candidate returns a checkable KKT certificate, and SLSQP does not.
  - The textbook projection-and-clip baseline breaks the balances on 9 of 10 seeds.
  - The honest default here is SLSQP. A useful next step is SLSQP's answer with a KKT certificate computed afterwards,
    as a composition.
- **`community_louvain`: higher modularity than CNM on all ten seeds** (mean 0.544 vs 0.516). Label propagation's
  mean is 0.401.
- **`blackbox_multistart_lbfgsb`: does not replicate #179's direction.**
  - Differential evolution wins 4 of the 6 multimodal seeds (Rastrigin, Ackley, Griewank, Styblinski-Tang at 2-10
    dimensions and 1000 evaluations per dimension). Multistart wins one unimodal seed.
  - #179's 26-8 used other objectives and budgets.
  - No parameter was tuned after seeing this result.
- **`crowd_weighted_vote`: beats Dawid-Skene on 9 of 10 seeds**, including all 5 sparse seeds, and is 30x faster.
  Dawid-Skene wins one dense binary seed.
  - This matches #179's sparse finding: Dawid-Skene lost 8/32, p = 9e-5.
  - The Dawid-Skene port treats each worker as its own independence group. #179 ran it on independence groups, and
    the two may differ.

## Seeds

- Development: 0-9.
- This lane's declared review range: 9300-9399. A search of every local branch found no seed declaration in
  9300-9399. The unit tests use 9300-9339 for reconciliation and 9300-9319 for the bin-packing bound.
- Not used: held-out admission seeds, P8's reserved seeds, and #179's newly reserved 6501-6840.

## Not built in this lane, and why

- **Centrality (betweenness / PageRank).** The coverage record's B12 wants a decision-relevant test: does centrality
  predict the exact cut's control points better than degree? That needs B05's natural import-graph family, which does
  not exist yet. A centrality genome without that test would be a number with no decision attached.
- **MCTS / beam search with exact DP truth, genetic algorithms, and property-based counterexample search.** These were
  deferred for time after the coordinator added two acquisition genomes. They are still ABSENT in the coverage record.
- **SAT as a separate decision family.** Weighted MaxSAT with hard clauses covers SAT as its feasibility case:
  `feasible: false` comes with a Z3 UNSAT proof. A plain-SAT genome would duplicate the operation.

## Limits stated in the genomes

- MaxSAT optimality rests on Z3's UNSAT verdict. No DRAT or VeriPB proof is checked.
- The reconciliation tolerances are relative: 1e-7 for feasibility and 1e-6 for KKT.
- Community quality is modularity, which is not ground truth, and it has a resolution limit.
- The black-box genome never claims a global optimum.
- The crowd vote assumes workers err independently.
