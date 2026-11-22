# SymbioSoup Stage A: results (seeds 0-7; more seeds running)

Pre-registration: [PREREGISTRATION.md](PREREGISTRATION.md), committed in `f08da790` before any run.
Implementation: `developmental/symbiosoup/` (CuBFF `bff_noheads` semantics reimplemented from commit
`f212e849`; zero mismatches against the specification interpreter). Settings as registered: 131,072 programs,
mutation 2^-12 per byte, 16,000 epochs, metrics every 128 epochs. Container: 4 CPU cores, about 11 minutes per
non-transitioning seed.

| seed | transition epoch (higher-order entropy >= 1.0) | at threshold 3.0 | maximum higher-order entropy |
|---|---|---|---|
| 0 | none by 16,000 | none | 0.38 |
| 1 | **15,744** | 15,744 | 3.91 |
| 2 | none | none | 0.36 |
| 3 | **7,680** | 7,808 | 4.03 |
| 4 | none | none | 0.36 |
| 5 | none | none | 0.36 |
| 6 | none | none | 0.37 |
| 7 | none | none | 0.37 |

**Primary outcome: 2 of 8 transition within 16,000 epochs, a rate of 0.25 with a Wilson 95% interval of
[0.07, 0.59].** The interval contains the reported 0.40, so the gate's **pass** condition holds. As
pre-registered, eight seeds can show consistency only; they cannot establish reproduction.

**The transitions are crisp, as the paper describes them:**

- Seed 3: higher-order entropy goes 0.13 → 2.95 → 3.97 across three checkpoints, operations per pair
  400 → 1,058 → 1,422, and Brotli bits per byte 6.2 → 1.35.
- Seed 1: higher-order entropy goes 0.10 → 3.66, and operations per pair 296 → 1,866.
- No non-transitioning seed exceeded 0.39, so the threshold choice (1.0 or 3.0) does not change any verdict.

**Not shown here:** replication measured directly (CuBFF's self-replication check was not ported; compression
is corroboration only, as the reports require); a differential run against the real CuBFF binary (its build
was refused in this session); the random-walk counterexperiment (arXiv:2607.01483); and the 50-100 seeds the
reports ask for.

Raw data: `canonical/runs-seeds-0-7.jsonl`, plus one `canonical/progress-<seed>.jsonl` per seed with every
checkpoint.
