# natops-2026-10-21: dependency control points in GREG's own repository (confirmatory run)

**Evidence label:** NATURAL repository data (this repository's import graphs at 22 first-parent commits, read from
git blobs), consequence-inert, exact mathematical truth. **Not external validation**, not admission, not adoption.

- Pre-registration: [`PREREGISTRATION.md`](PREREGISTRATION.md), committed in `29ea4ffc`.
- Freeze: [`freeze.json`](freeze.json), committed in `362780f2`, before any held-out instance was scored.
- Confirmatory run: once, from a clean tree at `362780f2`, under `taskset -c 1`. The gate passed, and the post-look
  re-check passed. Outputs: [`results.json`](results.json) (every row) and [`run.log`](run.log).
- Development (exploratory, not confirmatory): [`development.json`](development.json) and
  [`development-v1-degree-stage1.json`](development-v1-degree-stage1.json).
- Code: `cortex/evaluation/natural_ops/`. Tests: `tests/unit/test_natural_ops_family.py`.

## Question and instances

Each instance asks for a minimum set of intermediate modules whose removal leaves no import path from an entry
module S to a module T, that is, a minimum S-T vertex cut. The entry modules are `greg.cli`, `greg.missions`,
`greg.body`, `greg.gravity`, `greg.remote` and `greg.console`.

- **Pool:** 1,972 instances after deduplication. The split was by instance-id hash: 545 development and 1,427
  held-out.
- **Held-out items:** they come from 12 distinct commits. 141 have an organ or evidence target; 1,286 have an
  internal target.
- **Truth:** Menger augmenting paths and an exact HiGHS integer program agree on every item, with 0 truth
  disagreements.
- **Distribution of the minimum cut size k:** k = 1 on 943 items, 2 on 268, 3 on 110, 4 on 61, 5 on 21, and 6-13
  on 24.

## Results (held-out, n = 1,427)

| Arm | Path | Correct | Wrong (false) | Abstain (out of bounds / in bounds) | Translation failures | Median s | p90 s | CPU s total | Worker procs |
|---|---|---:|---:|---|---|---:|---:|---:|---:|
| `practitioner` (`networkx.minimum_node_cut`) | in process, bypasses `reason` | **1427** [0.997, 1.000] | 0 | 0 / 0 | none | 0.0013 | 0.0021 | 2.0 | 0 |
| `composition` (betweenness, k=1 certificate, else genome) | stage 1 bypasses `reason`; stage 2 `reason` | 1407 [0.979, 0.991] | 0 | 20 / 0 | 20 input-bounds | 0.0005 | 0.403 | 163.5 | 968 |
| `flow_maxflow` (admitted genome 1.0.1) | `reason` | 1402 [0.974, 0.988] | 0 | 25 / 0 | 25 input-bounds | 0.351 | 0.718 | 486.7 | 2854 |
| `compiled` (Competency Compiler) | `reason` | 1402 [0.974, 0.988] | 0 | 25 / 0 | 25 input-bounds | 0.350 | 0.730 | 487.5 | 2854 |
| `betweenness_greedy` | in process, bypasses `reason` | 1315 [0.906, 0.934] | 112 | 0 / 0 | none | 0.0004 | 0.0007 | 0.6 | 0 |
| `degree_greedy` | in process, bypasses `reason` | 1063 [0.722, 0.767] | 364 | 0 / 0 | none | 0.0002 | 0.0003 | 0.3 | 0 |

- **Reading the table:** brackets are Wilson 95% intervals. Money is $0 for every arm. There were no refutations
  and no arm exceptions.
- **Abstention quality:** every abstention by a `reason` arm was on an item beyond the genome's declared bounds
  (120 nodes, 400 edges after node splitting). No arm abstained on an in-bounds item, and no arm gave a false answer
  through `reason`. The greedy baselines never abstain; they are wrong instead.
- **Compiler routing:** the compiler selected `cognition.flow_maxflow` on all 1,427 items. Its results equal the
  genome's (0-0), at a latency ratio of 1.00.
- **The composition's stage 1** (the k = 1 certificate) decided 943 items. All 943 were correct.

## Verdict (pre-registered rule)

**LIFT.**

- **The comparison:** the best single constituent is `flow_maxflow`. Against it, the composition wins 5 items and
  loses 0. The one-sided exact sign test gives p = 0.031.
- **No added false answers:** the composition has 0 WRONG, as does `flow_maxflow`.
- **Latency:** the composition's median latency is 0.0014x the genome's (bootstrap 95% CI 0.0014-0.0015). It was
  faster on 1,207 items and slower on 220.

By the frozen rule this counts toward VPL. Read it with the following, all from `results.json`:

1. **The lift is from the genome's size bound, not from better cognition.** All 5 wins are among the 25 held-out
   instances that exceed `flow_maxflow`'s declared input bounds. They are the 5 with k = 1, which the
   betweenness-greedy stage certifies without the genome. On the 1,402 in-bounds items, the composition, the genome,
   the compiler and the practitioner are all correct on every item: a tie. The pre-registration declared this
   interpretation in advance. The genome's bound, not reasoning quality, decides the correctness comparison.
2. **The practitioner dominates every GREG arm.** `networkx.minimum_node_cut`, in process:
   - is correct on 1,427 of 1,427;
   - beats the composition 20-0 (Holm p < 1e-5) and the genome 25-0;
   - runs at about 1/263 of the genome's median latency through `reason`.

   The `reason` path's cost is mostly isolation and independent verification: two worker processes per call, about
   0.35 s.
3. **The cheap path is real.** Two-thirds of the items have a single point of failure. The betweenness baseline
   certifies these at about 0.4 ms with no false answers, because a single separating module is optimal whenever no
   direct edge exists. That is why the composition's median latency is 1.4 ms or less.
4. **Directive item 5's falsifier "the degree heuristic matches the exact cut on most instances" is MET.** Degree
   greedy is exact on 74.5% (1,063 of 1,427). Betweenness greedy is exact on 92.1%, but it gives 112 false answers,
   so neither baseline is safe without a certificate.

## Proposed routing (for review; nothing attached or changed)

- **Exact method in process:** for consequence-inert dependency control-point questions, use the exact min vertex
  cut (NetworkX, or the genome's algorithm) in process. Isolation and verification buy nothing measurable here.
- **When the canonical path is required:** if `reason` must be used (governed or consequence-bearing requests), run
  the k = 1 certificate first, then the genome.
- **Genome bounds:** raise or remove `flow_maxflow`'s 120-node and 400-edge bounds for unit-capacity node-split
  instances, so that the 25 oversized items are not abstentions. This is a genome change that needs its own
  admission; it is not made here.

## Limitations

- **Correlated items:** the same modules and paths recur across sources and commits. The sign tests assume
  independence, so p = 0.031 is optimistic. Programme-wide this is one more VPL family; a single LIFT is not
  general superiority.
- **Graph model:** the graph is an abstraction. Parent-package `__init__` execution is not modelled, every import
  (including lazy imports) counts as a dependency, and import failure is not the same thing as loss of the edge.
- **Timing:** latencies were measured on a shared 4-core machine at load average about 4 (other lanes running), on
  one pinned core. Ratios are robust; absolute values are noisy. The latencies of in-process arms and `reason` arms
  are not like for like.
- **The composition is an evaluation-level pipeline, not a registered recipe:** stage 1 bypasses `reason`, and it
  is not routed by the Competency Compiler.
- **Source selection:** the sources were chosen after looking at pool size statistics, though not at any truth or
  arm output. The development part was used to switch the composition's stage 1 from degree to betweenness.
- **Evaluation-only attachment:** the genome was attached only in memory, for evaluation; no body state changed.
