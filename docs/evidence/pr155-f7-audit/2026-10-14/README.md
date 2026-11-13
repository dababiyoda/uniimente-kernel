# Independent audit of F7 (PR #158, P6 v4) against its parametric min-cost-flow reference

Founder decision 2026-10-14 (Track B, `INTENT-20261014-MIND-LINEAGE-CONVERGENCE`): independently audit PR #158's
F7 result against its parametric min-cost-flow reference. Frozen evidence audited:
`docs/evidence/greg-composition-lift/2026-10-14-v4/results-v4.json` (#158, unmodified).

**Verdict: CONFIRMED.** On all 200 held-out items:

- the independent optimum equals the recorded truth on every item (200 of 200);
- every arm's recorded outcome and throughput reproduce;
- the summary counts reproduce exactly.

| arm | optimal | suboptimal | wrong |
|---|---:|---:|---:|
| graph_alone_greedy (best constituent) | 108 | 92 | 0 |
| optimize_flow_blind | 19 | 181 | 0 |
| shortest_path_upgrade (practitioner) | 70 | 130 | 0 |
| parametric_min_cost_flow (practitioner, truth algorithm) | 200 | 0 | 0 |
| static / routed composition, compiled | 200 | 0 | 0 |

## Why an audit was needed

F7's truth (`expansion_truth`), its scorer (`expansion_value`) and its practitioner reference
(`parametric_min_cost_flow`) share one algorithm family: NetworkX min-cost flow with bisection, and an
Edmonds-Karp in the same module. A defect there would have made the truth, the reference and every score
agree with each other and all be wrong.

## Method (frozen in `cortex/evaluation/pr155_f7_audit/freeze.json`, commit `49b2d58`, before the held-out run)

1. **Instances.** The 200 held-out items were rebuilt from the bundled SNDlib extract by the audit's own
   implementation of F7's declared rules: 80% module sizing, free capacity, K <= 4 shortest loop-free paths
   capped at 32 arcs, price = 1 + round(km/100), at most 20 units per arc, and a budget of 20 times the
   cheapest admissible path (Bellman-Ford here). No function of `run_v4.py` or `greg.cognition.genomes.flow`
   is imported.
   Identity check, which passed on every item:
   - every arm's recorded plan names exactly the rebuilt arcs;
   - the rebuilt no-lease throughput equals the recorded one;
   - the path count and arc count match.
2. **Optimum.** Each instance was solved as a mixed-integer program by HiGHS (`scipy.optimize.milp`, relative
   gap 0). The program maximises throughput F subject to:
   - arc flow at most free capacity plus leased units;
   - integer leased units in [0, 20];
   - flow conservation;
   - total lease price within the budget.

   HiGHS is a different solver family from network simplex and from the composition's CP-SAT. The MILP's own
   plan was re-checked by the independent max-flow and the budget.
3. **Rescoring.** Every recorded plan was re-scored with `scipy.sparse.csgraph.maximum_flow` and its own budget
   and bounds check.

The only component shared with F7 is NetworkX's Yen k-shortest-paths enumeration, used to build the admissible
arcs. The identity check against every recorded plan guards it.

Disclosures (also in the freeze):

- Before the freeze, the machinery was smoke-run on the 50 development items only, and every check matched.
- The held-out recorded outcomes were already public. This is an audit of recorded evidence, not a blind
  evaluation.

## What the audit does and does not change

- F7's VPL lift stands as recorded. Composition beats the best constituent 92-0 within the pre-registered
  latency rule.
- #158's own reading also stands. The lift is over GREG's repertoire at freeze time, not over an operations-
  research practitioner. Parametric min-cost flow ties the composition on every item, at a recorded median of
  0.0043 s against 1.28 s (about 300 times faster).
- #158 has since registered `flow_expansion_mcf`, a single certified intelligence built on that method. Under
  the founder's VPL definition ("beats the strongest single available intelligence"), the composition would
  then face it as a constituent. A tie at higher latency would remove F7's lift. That is an expectation, not
  evidence; claiming it needs a fresh pre-registered run.
- F7's truth remains a computed optimum of a declared planning model on real topology and loads. It is not a
  realised outcome.

## Files

- `results.json`: per-item independent optimum, recorded truth and per-arm reproduction, written once by
  `python cortex/evaluation/pr155_f7_audit/audit.py`, which refuses to overwrite and refuses changed frozen
  inputs.
- Data terms: the SNDlib extract carries no open licence. See the data-rights flag in
  `docs/collaboration/MIND-LINEAGE-RECONCILIATION-2026-10-14.md`.
