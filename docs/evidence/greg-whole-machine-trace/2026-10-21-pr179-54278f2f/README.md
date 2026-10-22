# Whole-machine trace re-run on PR #179's head `54278f2f`, 2026-10-21

The same script as [the original trace](../2026-10-21/README.md) (`scripts/greg_whole_machine_trace.py`), run unchanged from a clean detached checkout of #179 at `54278f2f`. That commit merges #158 at `fa0d92a0` and contains #179's fixes for the two gaps the original trace recorded.

- Run: Linux, about 50 s, source dirty false. `trace.json` is the full output. `--verify trace.json` reports that the chain is intact.
- **Result:** all nine demonstrations are DEMONSTRATED, at the same tiers as the original. Organ coordination stays IMPLEMENTED (contract and adapter only, synthetic fixtures, no organ process).
- **The two gaps, re-checked:**
  - **Settled outcomes only.** Mission 2's compiler competence basis for the formed SciPy assignment mechanism is `settled 1, correct 1` (Laplace 0.667). Only settled outcomes enter it.
  - **Ledger citations.** Mission 1's two answers each settled once against method and version: `critical-path` against `cognition.optimization` 0.2.0, and `shard-assignment` against the SciPy mechanism 1.18.1. Both are ledger events (seq 90 and 91) that the step cites by hash.
- **What did not change:** the cause of the changed decision in mission 2 is still mission 1's retained qualification plus the founder's attach. Settled outcomes enter the basis but did not themselves change a choice, and the trace says so.
- **Limits:**
  - It is signed with a per-run test key, not Alfonso's.
  - It is consequence-inert, so VEPMC stays 0.
  - The appraiser shares reviewed Kernel code; it is not an independent implementation.
