# P4 v3: the decisive conditional-competence retest, 2026-10-08

- **Pre-registration:** `5475f75`, before any held-out run.
- **Runner:** `cortex/evaluation/learned_routing/run_v3.py`.
- **Suite:** `suite-v3.json`, 191 held-out items.
- **Freeze:** `freeze-v3.json`.
- **Run:** a clean worktree at `5475f75`, pinned to CPU core 3. `results-v3.json` records `source_commit = 5475f75`.
- **First attempt:** a container restart killed it at held-out item 149, before any result was written. Its log is kept as `run-v3-interrupted-at-item-149.log`. The complete run restarted from scratch with nothing changed; its log is `run-v3.log` (exit 0).

**Rule (frozen):**

- Majority of 3 runs per arm and item.
- **REGRESSION** if conditional adds a wrong answer (majority or any run) or decides fewer correctly.
- **NO_GAIN** if correct counts are equal.
- **INCONCLUSIVE_UNDERPOWERED** if there are fewer than 6 discordant items.
- **GAIN** if conditional decides more correctly and the one-sided exact sign test gives p < 0.05.
- Otherwise **INCONCLUSIVE**.
- Anything but GAIN keeps the shadow default and demotes conditional formal-engine routing.

| Arm (majority of 3) | correct | wrong | no decision | median s |
|---|---:|---:|---:|---:|
| static (class default order) | **162** | 0 | 29 | 0.688 |
| class-learned | 160 | 0 | 31 | 0.687 |
| conditional-learned (hierarchical fallback) | 160 | 0 | 31 | 0.696 |
| Z3 first (fixed order) | 136 | 0 | 55 | 0.719 |
| CP-SAT first (fixed order) | 128 | 0 | 63 | 1.003 |
| oracle (correct under either fixed order) | 166 | | | |

Comparisons:

| Comparison | Verdict | Correct | Wins / losses | p (one-sided) |
|---|---|---:|---:|---:|
| conditional vs static (primary) | **REGRESSION** | 160 vs 162 | 6 / 8 (14 discordant) | 0.79 |
| conditional vs class | NO_GAIN | 160 vs 160 | 7 / 7 | |
| class vs static | REGRESSION | 160 vs 162 | 3 / 5 | |
| conditional vs Z3 first | GAIN | 160 vs 136 | 30 / 6 | 3.5e-5 |
| conditional vs CP-SAT first | GAIN | 160 vs 128 | 42 / 10 | 5e-6 |

Latency, conditional vs static, on the 154 items both decided: 61 faster, 63 slower, median difference 0.0 s (p = 0.61).

**Predeclared consequence, applied:** conditional formal-engine routing is demoted. The `shadow` default stays: the memory is observed and never applied by default. The memory is retained as evidence and as a substrate for wider repertoires. No code default changes, because the shadow default was already in force.

## What the result means

- **The regression is timing noise, not a worse choice.** On all 14 discordant items the conditional and static arms chose identical solver orders. The difference is repeat-to-repeat variation at the 1 s deadline: conditional had 30 items whose three repeats disagreed, static had 21.
- **The memory learned nothing the static policy lacks.** On the 10 development bin-packing items, Z3 and CP-SAT each decided 9, so it kept Z3 first. On held-out tight bin packing, CP-SAT first would have decided 36 of 47 against 33 for static. The development sample was too small to reveal a difference the held-out set contains.
- **Learning beats a fixed order, but not the class default.** Conditional routing beats either fixed order by 24 to 32 items, yet the static class-default order already captures the same per-class choices (Z3 for feasibility, CP-SAT for optimisation).
- **What the P4 exit would need instead:** a repertoire wider than two engines, development data large enough to separate them inside one class, and deadlines that are not at the edge of solve time. Until then, conditional routing is not worth its complexity.

## Limits (recorded in the results file)

- Bin-packing truth is a 20 s reference label, not a proof for every item. 3 held-out bin-packing items had no label and were excluded before the run.
- Feature buckets are v2's fixed log scale, deliberately not retuned.
- One container and one CPU budget. Three repeats reduce timing noise but do not remove it.
- With two engines only, the conclusion is about ordering Z3 and CP-SAT, not about conditional competence over a wider repertoire.
