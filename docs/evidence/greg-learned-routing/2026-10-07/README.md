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
