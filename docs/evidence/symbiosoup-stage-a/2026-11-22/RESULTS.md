# SymbioSoup Stage A: results (seeds 0-16)

Pre-registration: [PREREGISTRATION.md](PREREGISTRATION.md), committed in `f08da790` before any run.
Implementation: `developmental/symbiosoup/` (CuBFF `bff_noheads` semantics reimplemented from commit
`f212e849`; zero mismatches against the specification interpreter). Settings as registered: 131,072 programs,
mutation 2^-12 per byte, 16,000 epochs, metrics every 128 epochs. Container: 4 CPU cores, about 11 minutes per
non-transitioning seed. Seeds were run in order (0-16), and none was skipped.

| seed | first checkpoint >= 1.0 | at threshold 3.0 | maximum higher-order entropy | what followed |
|---|---|---|---|---|
| 0, 2, 4-12 | none by 16,000 | none | 0.36-0.38 | none of these eleven seeds exceeded 0.39 |
| 1 | 15,744 | 15,744 | 3.91 | sustained; ops per pair 296 → 1,866 |
| 3 | 7,680 | 7,808 | 4.03 | sustained; ops per pair 400 → 1,422 |
| 13 | 6,272 | 6,400 | 3.46 | sustained (2.80 → 3.39 → 3.46) |
| 16 | 3,712 | 3,968 | 3.52 | 1.26 → 0.94 → 3.52; ops per pair 250 → 1,381 |
| 14 | 6,400 | none | 1.06 | **transient:** 1.06 → 0.67 → 0.47; ops per pair fell |
| 15 | 4,992 | none | 1.04 | **transient:** 1.04 → 0.77 → 0.57; ops per pair fell |

**Primary outcome, as pre-registered (first checkpoint >= 1.0): 6 of 17 seeds, a rate of 0.35 with a Wilson
95% interval of [0.17, 0.59].** It contains the reported 0.40, so the gate **passes**.

**Robustness, reported and not decided:** seeds 14 and 15 crossed 1.0 for one checkpoint and decayed, with no
rise in operations per pair. They look like transient structure, not a phase transition. Without them the rate
is 4 of 17, 0.24, with a Wilson 95% interval of [0.10, 0.47], which still contains 0.40. The verdict does not
depend on them.

**Defects in this instrument, found by running it, for v2:**

1. The pre-registered 1.0 threshold is too low: it admits transient spikes. A sustained criterion (staying
   above the threshold for several checkpoints), or replication measured directly, is needed.
2. The runner stops two checkpoints after the first crossing, which censors exactly the data that would tell a
   transient from a sustained transition. The threshold-3.0 column cannot be read for seeds 14 and 15 because
   of this. A v2 should run every seed to 16,000 epochs.
3. Seed 8's first attempt was interrupted at epoch 15,232 because the process was started outside the
   session's background mechanism. The partial file is kept (`canonical/progress-8.interrupted-at-15232.jsonl`).
   The rerun reproduced it checkpoint for checkpoint (deterministic), then finished without a transition.

**What this shows:** a CuBFF-semantics soup at canonical scale produces spontaneous, crisp jumps in
compressible structure and operations per pair, at a rate consistent with the reported one. **What it does not
show:** that the structures replicate (CuBFF's replication check was not ported; compression only
corroborates), agreement with the real CuBFF binary (its build was refused in this session), the random-walk
counterexperiment (arXiv:2607.01483), or the 50-100 seeds the reports ask for.

Raw data: `canonical/runs.jsonl` (all 17 seeds), `canonical/runs-seeds-0-7.jsonl` (the interim snapshot), and
`canonical/progress-<seed>.jsonl` with every checkpoint.
