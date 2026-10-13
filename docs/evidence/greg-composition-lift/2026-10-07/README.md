# P6 cognitive composition lift: first Verified Polyintelligence Lift measurement, 2026-10-07

Runner `cortex/evaluation/composition_lift/run.py`; suite `suite.json` (generated; dev seeds 1-8, held-out
9-24 per family); freeze `freeze-v1.json` written before the held-out run. Every arm ran through
`greg.cognition.cortex.reason` (bounded isolated worker): real Fermi, causal (stratified adjustment) and
CP-SAT/Z3 organs. Composition: `greg/cognition/composition.py`.

| Family (16 held-out each) | Arm | correct | wrong | suboptimal | no decision | median s |
|---|---|---:|---:|---:|---:|---:|
| F1 estimate -> optimize | estimate alone | 0 | 0 | 0 | 16 | 0.49 |
| | optimize at point estimate | 2 | **14** | 0 | 0 | 0.88 |
| | optimize at worst case (best constituent) | 2 | 0 | 14 | 0 | 0.87 |
| | static composition | 15 | 0 | 1 | 0 | 1.33 |
| | **routed composition** | **15** | **0** | 1 | 0 | 1.31 |
| F2 identify -> optimize | identify alone | 0 | 0 | 0 | 16 | 0.56 |
| | optimize on association (best constituent) | 11 | **5** | 0 | 0 | 0.74 |
| | static composition (fixed to F1's recipe) | 0 | 0 | 0 | 16 | 0.01 |
| | **routed composition** | **15** | **1** | 0 | 0 | 1.24 |

**VPL = 1 of 2 families.** F1: 13 wins, 0 losses, one-sided sign test p = 0.00012 -> lift. F2: 4 wins,
0 losses, p = 0.0625 -> **not lift under the frozen rule** (composition cut wrong allocations from 5 to 1,
but 16 items are too few for the threshold). Geometry routing over the best single fixed recipe: 30 vs 15
correct of 32 (the static recipe was chosen on development data: both recipes tied at 8/16, the
tie-break picked `estimate_then_optimize`).

## Failures, named

- `F1-16` suboptimal: the true p95 is 158.8 h, so 4 full-time staff (160 h) suffice; the estimate organ's
  Monte Carlo high landed above 160 and the plan added a part-timer (cost 4855 vs optimum 4272, over the
  1.10 tolerance). Sampling error at a capacity step.
- `F2-21` wrong: the identified effects ranked the programs like the confounded association did; the
  stratified estimate on 400 rows was not precise enough to separate them at the budget's integer margin.
- The point-estimate optimizer is the dangerous constituent: 14 of 16 plans claim a coverage they lack.

## Limits

- The families are constructed to need two intelligences. VPL > 0 here shows GREG's composition machinery
  delivers the complementary answer faithfully and fewer false answers than any constituent; it is not
  evidence that naturally occurring founder tasks need composition. That needs founder-used missions.
- F1 truth assumes the stated intervals are calibrated lognormal 90% intervals (the organ's semantics).
- One container; latency figures are this machine's.
