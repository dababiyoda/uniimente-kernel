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
