# SymbioTape Stage A

This test-only research track implements the founder's November 22 technical
report ([task #353](https://github.com/dababiyoda/uniimente-kernel/issues/353)).
It is separate from the proof-repair experiment (#350/#351) and from the
governed GREG runtime. The research destination is an experimentally
verified library of computational primitives for compositional individuality,
ecological adaptation, and cognition. The first dependency is an independently
implemented, deterministic interpreter with a trusted comparison.

Oracle: unmodified headed `bff` **pair interpreter** in
[CuBFF f212e849](https://github.com/paradigms-of-intelligence/cubff/tree/f212e849027c98fcf4b242eccfb5fed435223e23).
The complete population model, the headless variant and the report's future
energy-aware ISA are distinct contracts. Preserve variants in receipts.

## Gate fixed before the run

- Match the oracle's final 128 bytes and its active-operation count for every
  deterministic test pair. One mismatch fails parity; print its index, input,
  cap and both results. The Rust VM separately accounts for every fetched
  byte against fuel, including inert bytes. Oracle output counts only active
  operations.
- Use 10,000,000 deterministic generated pairs, seed 20261122. Every eighth
  case uses operator-rich tapes; other cases span all byte values. Cycle caps
  through 0, 1, 16, 128, 512, and 8192. Compare bytes directly case by case.
- Exercise zero followed by a write, byte wrap, head wrap, live forward/back
  scans, invalid brackets, and bounded loops. Re-run the exact test commands.
- Run at least one small pinned upstream population smoke case if available.
  Development smoke is not comparable to the 1,000-run paper distribution.
  Freeze the exact variant, schedule, detector, censoring and an equivalence
  margin before a powered replication. Interval overlap alone is not a
  replication criterion.
- A later random-walk comparison must use the same detector and count actual
  proposed mutations and evaluation work. Measure origin separately from
  takeover. Follow the opposing [2026 result](https://arxiv.org/abs/2607.01483).

## Two strengthening passes

**Pass 1.** The founder-intent lens preserves endogenous construction as the
target. The architecture and maintenance lenses keep the evaluator in the
existing test area with a single Rust interpreter and no package dependencies.
An upstream-only reproduction is the strongest simple option and remains the
population baseline. Doing nothing preserves earlier proof repair with no
evidence for mutable tapes. An independent port is useful only because it can
test future experimental changes against a pinned baseline. Its liabilities
are semantic drift and a long run too early. Pin upstream and separate a
pair-parity gate from a staged population budget.

**Pass 2.** The adversarial and evidence/welfare lenses reject an entropy-only
detector, a permissive mismatch threshold, and an execution path from
experimental bytes to the host. Use direct pair comparison, targeted cases,
bounded numeric memory, and independent population controls. Evolved bytes
remain interpreter data. The test build is reversible; close the draft or
revert its commits and retain all evidence. Residual dissent: pair parity is
compatible with population-level disagreement and offers no measurement of
symbiogenesis or intelligence. Revisit at a separately specified, powered
population result. **Disposition: EXPERIMENT.** No production authority,
deployment or purchase is part of this increment.

## Expanded parity gate

The initial headed corpus matched all 10,000,000 pairs. Two limitations
require expansion before using this port for paper replication. Section 2 of
the paper initializes both heads and the instruction pointer at zero, which
matches `bff_noheads`. The headed and headless variants require separate
receipts. Also, the original generator tied two cycles with a common divisor:
every eighth case was operator-rich, while fuel was selected modulo six, so
operator-rich inputs missed three caps. Keep the initial result as qualified
evidence. In the expanded corpus select the cap by group of eight, so both
input distributions visit all caps. Require 10,000,000 zero-mismatch pairs
**per variant** on the expanded protocol.

## Results and reproduction

| Check | Result |
| --- | --- |
| Expanded headed oracle comparison | 10,000,000 of 10,000,000 pairs matched. |
| Expanded headless oracle comparison | 10,000,000 of 10,000,000 pairs matched. |
| Rust targeted tests | 6 passed. |
| Headed population smoke | 512 randomly initialized tapes, seed 20261122, two CPU threads. The two CSVs matched byte for byte; zero positive upstream detector flags at recorded callbacks through epoch 65. |
| Headless population sizing | 131,072 tapes, the same seed, four CPU threads. 8.688 seconds on this host through the epoch-129 callback. Detector disabled for sizing. |

Toolchain: Rust 1.85.1 (4eb161250), GCC C++ 14.2.0, libbrotli, Linux x86-64.
Oracle source digests: `bff.inc.h`
`cf72e2a9b2666961c59a493e642aba64cce609bb18be4a0b33f13bdf771d4a0e`;
`common_language.h`
`d07f7bfb2c9717eb58f681b4c9523e5c7b9b17694977fe0bb11d5f10542aacc5`.

From this directory, with the pinned upstream checkout already present and
a Rust compiler, C++ compiler with OpenMP and Brotli headers installed:

```bash
bash parity.sh /absolute/path/to/cubff 10000000
```

The harness compiles the actual upstream interpreter without edits and
streams each input and expected result to the Rust reference. The runner
compares actual output byte for byte; it rejects missing or extra records.
Byte zero is inert during ordinary instruction fetch, still consumes fuel,
and is tested by brackets. Backward jumps resume after the matching opening.
The Rust library has no host interfaces available to the interpreted tape.

For the population probes, build the pinned checkout with `make CUDA=0`
and run these commands from that checkout:

```bash
OMP_NUM_THREADS=2 bin/main --lang bff --seed 20261122 --num 512 \
  --max_epochs 63 --print_interval 16 --eval_selfrep --disable_output --log headed-smoke.csv
OMP_NUM_THREADS=4 bin/main --lang bff_noheads --seed 20261122 --num 131072 \
  --max_epochs 127 --print_interval 128 --disable_output --log headless-sizing.csv
```

The upstream CLI checks the epoch limit at callbacks and stops when the
reported epoch is greater than the supplied limit. The logs retain observed
epochs. The small run tested deterministic startup and logging. It cannot
estimate population transition rates. An early, linear extrapolation of the
sizing run is about 18 minutes per seed at 16,000 epochs; later tape dynamics
and replicator measurements can materially change runtime. No estimate is
offered for a later optimized implementation.

## Handoff

1. Pin and document the exact paper-reproduction settings and the detector's
   false-positive and false-negative controls. Preregister a precision or
   equivalence target and preserve origin versus takeover separately.
2. Run a short independent pilot to measure actual cost with the detector.
   Use that result to budget the paper-scale replication and disclose
   censoring. The current smoke and sizing runs are insufficient for it.
3. In a separate work slice, freeze the interactive versus random-walk
   comparison before examining outcomes. Record common mutation counts,
   candidate evaluations, and interpreter work. Keep the cheaper explanation
   if it fits the data. Ecology and cognition depend on this distinction.

Claims and handoffs belong on [#353](https://github.com/dababiyoda/uniimente-kernel/issues/353).
Keep experimental byte state and production authority separated. Production
integration would require a distinct evidence-backed intake decision.
