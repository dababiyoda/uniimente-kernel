# SymbioSoup Stage A: pre-registration (written before any run)

**Directive.** The two research reports of 2026-11-22, adopted by the founder as directive instructions
([sources](../../../intent/sources/mind-research-2026-11-22/README.md)). Their first gate is to reproduce the
canonical CuBFF phenomenon before inventing anything.

**Substitution, disclosed.** CuBFF itself could not be built: this session's permission policy refused
installing `libbrotli-dev` and building the third-party binary. Instead,
`developmental/symbiosoup/bff_ref.c` reimplements its `bff_noheads` soup from the source at commit
`f212e849` (Apache-2.0): the same operations, the same SplitMix64 streams for initialization, shuffling and
mutation, the same 64-byte programs, the same 8192-step cap and the same mutation probability (2^18/2^30). It
is checked against a slow specification interpreter (`spec.py`). This is therefore a reproduction of CuBFF's
**semantics**, not of its binary. A differential run against the real CuBFF stays owed.

**Fixed settings.** 131,072 programs; mutation 2^-12 per byte per interaction; metrics every 128 epochs (the
CuBFF default): h0, Brotli q2/lgwin24 bits per byte, and higher-order entropy = h0 - bpb. Each run stops at
16,000 epochs, or two checkpoints after a transition.

**Primary outcome.** A run *transitions* at the first checkpoint whose higher-order entropy is >= 1.0. The
outcome is the fraction of seeds that transition within 16,000 epochs, with a Wilson 95% interval.

**Comparison.** The reports state that about 40% of 1,000 runs transitioned within 16,000 epochs at 0.024%
mutation. That figure was not checked against the paper in this session. **Pass** if the Wilson interval
includes 0.40. **Fail** if it excludes 0.40. With the few seeds this container can run, the interval will be
wide; a pass then shows only consistency, not reproduction.

**Sensitivity, reported and not decided:** a threshold of 3.0 (a third-party heuristic the reports call
non-canonical), and the ops-per-pair jump.

**Seeds:** 0, 1, 2, ... in order, as many as the time allows. None is skipped or chosen after the fact.

**Kill/negative rule:** every seed run is reported, including runs that time out.
