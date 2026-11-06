# Layer 1, 2 and 4 ABSENT families, batch B (2026-10-21)

**DEVELOPMENT ONLY.** Every number here comes from development seeds 0-9 (`admission --dev`). The unit tests also run
checks on this lane's declared review range, 9400-9439. These numbers are **not admission evidence**: the genomes were
built and inspected on these same seeds. Nothing here is admitted or attached. Each family is registered **withheld**
(`VERIFIED`), and attaching one is the founder's decision.

- Branch: `lane/l124-absent`, based on `b67db40c`.
- Code commit: `ec665c28`.
- Dev outputs: `dev/*.json`, verbatim from `python -m greg.cognition.genomes.admission --dev FAMILY`, each run pinned
  with `taskset -c 0`.
- Host load: the 1-minute load average read 3.16-3.19 during the runs, on 4 cores, with two other Python processes
  running on other cores. Wall-clock latencies may be inflated. `diagnostics.median_cpu_seconds` in each file gives
  the CPU clock, which agrees with the wall clock to within 3% for every arm.

## Declared seeds

- Development: 0-9.
- This lane's declared review range: **9400-9439**. It is declared here before any instance of it is committed.
  `scripts/data_exposure_ledger.py` lists it in `DECLARED_DEV_RANGES`.
  - A seed-context grep of every local branch found no other declaration or use of 9400-9439.
  - The unit tests use all 40 review seeds for the token bucket and the auction checks.
- Never generated: 1000-1029, 1100-1129, 1200-1399, 1400-1429 (proposed held-out, see the draft below), 3000-4999,
  5001-5040, 6501-6840, 7000-9199 and 9300-9339.

## What was built

The 2026-10-21 coverage record (`docs/collaboration/MIND-COVERAGE-2026-10-21.md`) lists these as ABSENT, and section
31 condition 1 names each as a family with no executor:

- Layer 1: "rate control" and "evaluate small local learners";
- Layer 2: "ecology bidding" (the ecological requirement is INTEGRATED only through admission statuses, and "methods
  do not bid");
- Layer 4: "graph diffusion".

Effect, not metaphor (`docs/FOUNDER_EFFECT_COMPILER.md`): each family is an ordinary, named mechanism with a measured
effect on a behaviour GREG needs. None simulates biology.

Every family:

- has an independent verifier that recomputes the answer or checks a certificate, never trusting the solver's claim;
- passes the library-wide test that corrupts each single leaf of an answer, so a corrupted answer is refuted;
- has a strongest available competitor and a simple baseline, both deployable;
- has a seeded instance generator and a declared benchmark world in `greg/cognition/worlds.py`;
- is reachable through `greg.cognition.cortex.reason` and the Competency Compiler by its inputs (tested with an
  in-memory attach only).

| Family (operation) | Layer | Mechanism | Independent verifier | Baseline | Competitor | GREG need |
|---|---|---|---|---|---|---|
| `basal_token_bucket` (`rate_limited_admission`) | 1 | Token bucket (starts full, continuous refill). The admission threshold rises as the bucket empties: a request is admitted iff a token is available and its rank among the last 256 values is at least 1 - fill. | Arrival-curve conformance (every k+1 consecutive admissions span at least (k+1-b)/r), written apart from any bucket simulation; count and value recomputed; the declared rule replayed by separate code. | Plain token bucket | Online bid-price control (revenue-management fluid approximation over the refill horizon) | Admitting jobs or API calls under a provider's rate contract so nothing is refused, while protecting tokens for valuable work |
| `basal_nlms` (`online_linear_predict`) | 1 | Normalised LMS, mu 0.5, zero start, bias feature | Independent vectorised NumPy replay of the declared update (predictions and final weights); prequential error recomputed | Running mean of the targets | Recursive least squares, forgetting 0.995 | Predicting a job's run time or cost from its features, learning from each realised value |
| `collective_auction` (`capacitated_task_allocation`) | 2 | Bertsekas forward auction with epsilon scaling on the square slot problem (tasks + dummies against agent slots + null slots) | Capacities and value recomputed; a weak-duality bound computed from the certified prices must exceed the value by less than one, which proves optimality for integer values | Greedy by value | Central planner: SciPy `linear_sum_assignment` on the expanded slot matrix | Allocating queued work to capacitated workers or methods by competence, with prices that state each slot's marginal value |
| `develop_diffusion` (`propagate_graph_labels`) | 4 | Harmonic label propagation: local Jacobi sweeps, seeds clamped, until no score moves by more than 1e-11 | Per connected component, the harmonic Dirichlet system solved directly (dense NumPy); scores within 1e-6, labels its argmax, seedless components abstain | Nearest seed by hop count | Central structural method: Louvain communities, each labelled by its seeds' majority | Spreading a few verified claim labels over a support or dependency graph |

How each family's ground truth is computed, independent of every arm:

- **Token bucket:** the offline (hindsight) optimum by SciPy HiGHS on a 0/1 program with explicit token states. The
  tests check that it bounds every online policy on all 40 review seeds.
- **NLMS:** the realised targets of the generated stream. Quality is minus the prequential MSE over the target
  variance.
- **Auction:** the transportation LP in SciPy HiGHS. The matrix is totally unimodular, so the LP optimum is integral.
  The auction matches it on all 40 review seeds, and its dual bound proves it on each.
- **Diffusion:** the planted classes. Quality is accuracy on the non-seed nodes.

## Development results (seeds 0-9; not evidence)

Wins, losses and ties are on the genome's native quality. Latency is the median wall-clock time. "Would be" is what the
frozen rule (`RULE`, unchanged) gives on these ten seeds. It is not an admission verdict.

| Family | vs baseline (W-L-T) | vs competitor (W-L-T) | Wrong answers: cand / base / comp | Mean quality: cand / base / comp | Median latency: cand / comp | Would be |
|---|---|---|---|---|---|---|
| `basal_token_bucket` | 8-2-0 | 5-5-0 | 0 / 0 / 0 | 0.920 / 0.668 / 0.874 | 0.32 ms / 1.03 ms | EXPERIMENTAL |
| `basal_nlms` | 10-0-0 | 3-7-0 | 0 / 0 / 0 | -0.066 / -1.012 / -0.111 | 2.7 ms / 7.0 ms | DEFAULT_FOR_GEOMETRY |
| `collective_auction` | 10-0-0 | 0-0-10 | 0 / 10 / 0 | 1.000 / 0.985 / 1.000 | 20 ms / 0.79 ms | SUPERSEDED |
| `develop_diffusion` | 4-6-0 | 1-9-0 | 0 / 0 / 0 | 0.634 / 0.708 / 0.785 | 10 ms / 6.6 ms | EXPERIMENTAL |

Who won, plainly:

- **`basal_token_bucket`: no significant edge on ten seeds.**
  - Under overload it beats the plain bucket on all 8 overload seeds and the bid-price competitor on 5 of 8.
  - Under underload it loses to both on both seeds, by 0.5-1.4% of the optimum. After a burst it refuses low-value
    requests that the contract would have allowed. That is a real cost of the rule, recorded as a failure mode.
  - The 8-2 record against the baseline gives p = 0.055, just short of 0.05, so the rule calls it EXPERIMENTAL.
  - It reaches 92% of the hindsight optimum on average, against 87% for bid-price control and 67% for the plain
    bucket.
- **`basal_nlms`: RLS wins more seeds; NLMS wins on average.**
  - RLS has the lower prequential error on 7 of 10 seeds: both drifting, both heavy-tailed and both
    correlated-feature streams, and one of the two stationary streams.
  - NLMS wins 3 seeds: both abrupt-switch streams and one stationary stream. The likely causes, not separately tested, are
    RLS's slow re-adaptation after a switch (forgetting 0.995 is a memory of about 200 samples) and its early
    transient from P0 = 1000 I.
  - Those three RLS losses are large (normalised error 0.20-0.28 against 0.04-0.06), so NLMS has the better mean.
  - The 3-7 record is not significant (p = 0.17), and NLMS is 2.6x faster, so the rule would call it DEFAULT. The rule
    counts seeds, not error sizes; a held-out run decides it.
- **`collective_auction`: SUPERSEDED by the central planner.**
  - It is exact on all ten seeds, as is `linear_sum_assignment`, but the compiled central solver is 25x faster than the
    pure-Python auction.
  - Greedy is never optimal (98.5% on average), so every greedy answer counts as wrong.
  - What the rule does not count: the auction returns clearing prices and a dual certificate anyone can recompute;
    `linear_sum_assignment` returns neither. A next step is the central answer with prices computed afterwards (LP
    duals), as a composition.
- **`develop_diffusion`: loses to both.**
  - Louvain communities with a seed vote win 9 of 10 seeds (p = 0.011). The nearest seed wins 6 of 10.
  - This is the known failure of harmonic propagation with very few seeds (2-6% of nodes, or one per class). The
    solution flattens toward the seeds' proximity and degree rather than the cluster structure, and imbalanced seeds
    pull the argmax toward the seeded majority.
  - Class mass normalisation (Zhu et al. 2003) is the standard correction. It was **not** added, because it would be
    tuning after seeing these results. If it is tried, it should be a new version with its own pre-registration.

## Design history, disclosed

- No parameter of any of the four families was changed after its dev results were seen. Before the dev runs, a quick
  sanity script printed per-seed qualities for all four on seeds 0-9; no code changed after it except the next item.
- After that script, the token bucket's evaluation-side optimum was wrapped so that HiGHS's MIP diagnostics, printed
  on the C stdout, do not corrupt `--dev` JSON output. This does not change any value.
- The auction's second-best bid computation was rewritten before any run, for clarity.

## Limits stated in the genomes

- The token bucket makes no optimality claim. Its evidence is a control trace: conformance and a replay. It reads only
  the last 256 values, so it follows a value shift with a lag. The contract is the declared one, and a provider that
  enforces a different window can still refuse requests.
- NLMS's mu 0.5 is fixed, not tuned to the stream. The model is linear in the given features.
- The auction needs integer values for its optimality proof. It is pure Python, and price wars on near-ties cost bids.
- Diffusion scores are first-passage probabilities, not probabilities that a label is true. Heterophilous graphs
  defeat it, and it is slow on poorly connected graphs (UNKNOWN at the sweep cap).
- Every benchmark here is generated. Three are simulated worlds and one (the auction) is a mathematical instance, as
  `greg/cognition/worlds.py` declares. None measures competence on GREG's real queue, jobs or claim graph, and no
  such data exists in this repository yet.

## Not built in this lane, and why

- **Cellular-automaton local-rule repair (L4)** and **differentiation (L4)** need a target-structure geometry with a
  central-planner competitor. `develop_repair` already measures local repair against a central replanner on a lattice,
  so a cellular automaton on the same lattice would mostly duplicate that comparison. They are still ABSENT in the
  coverage record.
- **Active inference (L1/L4)** would need a generative model of a process GREG actually controls. Built against
  Kalman/PID on simulated plants, it would duplicate `basal_kalman` and `pid_simopt` with a different label.
- **Associative microcircuits / networks (L1)** and the **global workspace (L5)** have no decision-relevant GREG
  geometry identified yet. A Hopfield memory without a retrieval task GREG performs would be a costume.
- **Immune tolerance (L2)** was not attempted in this lane.

These remain on the coverage record as ABSENT. This lane's prose does not change that record.
