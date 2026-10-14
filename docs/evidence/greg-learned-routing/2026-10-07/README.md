# P4 learned routing: frozen held-out comparison, 2026-10-07

Runner `cortex/evaluation/learned_routing/run.py`, suite `suite.json` (90 generated items with ground
truth: pigeonhole, disjunctive schedules, planted integer equalities, knapsack feasibility and
optimization; seeds 1-3 development, 4-6 held out), freeze `freeze-v1.json` written before the held-out
run. Equality sizes were reduced from (10, 16, 22) to (4, 6, 8) on development seed 1 only, before the
freeze, because both engines timed out on every larger system. Budget 3 s per item, real Z3 5.1 and
CP-SAT 9.15 in one Linux container.

| Arm (45 held-out items) | correct | wrong | no decision | median s |
|---|---:|---:|---:|---:|
| static (cortex 0.2.1 policy) | 39 | 0 | 6 | 0.615 |
| learned (ledger from 90 settled dev runs) | 41 | 0 | 4 | 0.598 |
| z3_first (reference) | 34 | 0 | 11 | 0.617 |
| cpsat_first (reference) | 32 | 0 | 13 | 1.549 |

**Verdict (frozen rule): INCONCLUSIVE** (2 wins, 0 losses, one-sided sign test p = 0.25).
**Substantive reading: no routing gain.** The ledger's learned order equals the fixed policy in both
geometries, so both arms ran the same engines; the two discordant items (`equalities-8-5`,
`equalities-8-6`) are Z3 finishing at 2.7-2.9 s against the 3.0 s budget in one arm and not the other.
The P4 exit ("learned routing beats the static baseline on held-out tasks") is **not met**.

What the run does establish: the fixed per-query-kind policy beats either single engine order by
5-7 decided items with no wrong answers, and GREG's outcome memory, trained only on settled outcomes,
found no evidence to override it and therefore did not move it (no regression, no authority change).

## Negative evidence

- CP-SAT ran 9.8 s against a 3 s latency budget on development item `pigeonhole-6-1` (calibration run).
  The router's budget is advisory to that engine on this instance; recorded for the cortex owners.
- Competence is pooled per epistemic class (the frozen 0.2.1 ledger key). Knapsack feasibility (Z3 wins)
  and pigeonhole-7 (CP-SAT faster) share one learned order; finer conditions would need a new ledger
  version.
- Ground truth stands in for the signed check plus separate-process appraisal GREG requires in production.
- The ledger learns decided/undecided and correct/wrong, not latency.

# P4 v2: conditional competence memory (same day, founder review of #155)

Runner `cortex/evaluation/learned_routing/run_v2.py`; suite `suite-v2.json` (v1 families + knapsack
feasibility at 1 s + tight bin packing at 1 s, reference-labelled by both engines at 20 s; 2 unlabelled dev
items excluded); freeze `freeze-v2.json`, committed before the held-out run (`557fd77`). Memory:
`greg/cognition/conditional_competence.py` (features from the signed formal model, hierarchical fallback,
>= 3 weighted outcomes and a 0.10 gap to move a default). Results: `results-v2.json`.

| Arm (66 held-out items) | correct | wrong | no decision | median s |
|---|---:|---:|---:|---:|
| static (cortex 0.2.1 policy) | 56 | 0 | 10 | 0.603 |
| class_learned (v1 ledger) | 56 | 0 | 10 | 0.598 |
| **conditional_learned** | **57** | **0** | **9** | 0.540 |
| z3_first (reference) | 49 | 0 | 17 | 0.642 |
| cpsat_first (reference) | 44 | 0 | 22 | 1.006 |
| oracle: correct under either fixed order | 59 | | | |

**Verdict (frozen rule): INCONCLUSIVE** for conditional vs static (3 wins, 2 losses, p = 0.5) and for
conditional vs class (2 wins, 1 loss, p = 0.5); class vs static NO_GAIN. The P4 exit is **not met**.

What the memory did learn, per sub-region (all inside one epistemic class, `constraint_feasibility`):

| Family | static | class | conditional | z3_first | cpsat_first |
|---|---:|---:|---:|---:|---:|
| tight bin packing, 1 s (n = 12) | 7 | 7 | **9** | 6 | 9 |
| knapsack feasibility, 1 s (n = 9) | 9 | 9 | 9 | 9 | 3 |
| knapsack feasibility, 3 s (n = 9) | 9 | 9 | 9 | 9 | 3 |
| knapsack optimisation (n = 9) | 9 | 9 | 9 | 3 | 9 |

The conditional memory put CP-SAT first on bin packing (decided at the exact cell for <= 300 variables and
at `kind+ops+domain+budget` for the sparse 384/600-variable cells; CP-SAT 0.99 / 0.89 vs Z3 0.67 / 0.70)
and kept Z3 first on knapsack feasibility, so it matched the better fixed order in each sub-region, which
neither fixed order nor the class ledger does. The held-out margin is too small to separate from noise.

## Negative evidence

- Timing noise at the 1 s boundary is as large as the effect: the same Z3-first order decided
  `binpack_tight_1s-24x6-5` in one arm (0.68 s) and timed out in another (1.02 s); `equalities-8-5` was lost
  by the conditional arm with the static order (Z3 at 3.0 s vs 1.8 s elsewhere). Single runs per item cannot
  resolve a one-item difference.
- The 384- and 600-variable bin-packing cells (where the probe showed opposite winners) share the
  `<=1000` size bucket; the frozen log-scale buckets did not separate them.
- 2 development bin-packing items had no 20 s reference label and were excluded.

## P4 v3: the one pre-registered decisive retest (2026-10-14)

Runner `cortex/evaluation/learned_routing/run_v3.py`; suite `suite-v3.json` (130 fresh held-out items, seeds
7-12, every v2 family; 2 bin-packing items had no 20 s reference label and are excluded and listed); freeze
`freeze-v3.json` committed before the run (`e2ea4c1`). Memory, features, buckets, thresholds and training
data are v2's, unchanged. The timing-sensitive arms ran 3 times per item in rotated order (majority decides);
every run's latency is kept. Results: `results-v3.json`. The run started at `e2ea4c1`; it records
`bfb9c04` because two unrelated commits landed while it ran; every pinned input is byte-identical there
(re-checked against the manifest after the run).

| Arm (130 held-out items) | correct | wrong | no decision | median s | p90 s |
|---|---:|---:|---:|---:|---:|
| static (cortex 0.2.1 policy) | 111 | 0 | 19 | 0.916 | 3.014 |
| class_learned (v1 ledger) | 109 | 0 | 21 | 0.927 | 3.018 |
| conditional_learned | 111 | 0 | 19 | 0.923 | 3.020 |
| z3_first (reference) | 96 | 0 | 34 | 0.984 | 3.015 |
| cpsat_first (reference) | 84 | 0 | 46 | 1.006 | 3.022 |
| oracle: correct under either fixed order | 115 | | | | |

**Verdict (frozen rule): conditional vs static NO_GAIN** (111 = 111; 3 wins, 3 losses, p = 0.66). Class vs
static: **REGRESSION** (109 vs 111). Conditional vs class: INCONCLUSIVE (5/3, p = 0.36).

Every one of the 6 discordant items between conditional and static had split repeat runs (for example
`binpack_tight_1s-48x8-9`: static correct/correct/none, conditional none/correct/none): the difference is
1-second timing noise, not routing. On tight bin packing the learned CP-SAT preference reached 14 of 22, the
same as static, while the fixed CP-SAT-first order reached 15; the headroom over static on the whole suite is
4 items (oracle 115).

**Decision, as the founder instructed: conditional solver learning is not currently worth its complexity
for this two-engine repertoire.** P4's exit is not met after three frozen comparisons (v1 INCONCLUSIVE,
v2 INCONCLUSIVE, v3 NO_GAIN). Dispositions:

- `learned` routing mode: not recommended; it stays available behind the explicit mode switch and never
  becomes a default from this evidence.
- `shadow` (the default) is retained: it changes no execution and records, on every real mission, whether
  the memory would have chosen differently. That is the only route by which this mechanism could earn its
  place again (the P4 review trigger is 20 settled real-mission outcomes in one geometry); synthetic suites
  have now been exhausted three times.
- Nothing is deleted: the memory, the suites and all three verdicts remain as institutional evidence and as
  the substrate P8 searches over.
