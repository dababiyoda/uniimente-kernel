# P6 v2 composition lift: the second Verified Polyintelligence Lift measurement, 2026-10-08

- **Runner:** `cortex/evaluation/composition_lift/run_v2.py`.
- **Suite:** `suite-v2.json`.
- **Freeze:** `freeze-v2.json`, committed in `07350d4` before any held-out arm ran. The first freeze, `1ec8df5`, compared JSON lists with tuples and refused to run at all; the re-freeze changed nothing else.
- **Run:** a clean worktree at `07350d4`, CPU cores 0-2. The results record `source_commit = 07350d4`.
- **Path:** every arm ran through `greg.cognition.cortex.reason`, with isolated workers and an independent verifier per stage. Genome families were attached in an evaluation-only registry view.
- **Static composition:** dev selection picked `forecast_then_allocate` (9 correct development decisions). That recipe abstains on every other family.

| Family (held out) | Arm | correct | wrong | suboptimal / no decision | median s | stages |
|---|---|---:|---:|---:|---:|---:|
| **F2R** identify -> optimise (replication, n = 64) | identify alone | 0 | 0 | 64 nd | 0.47 | - |
| | optimise on association (**best constituent**) | 48 | **16** | 0 | 0.56 | 1 |
| | static composition | 0 | 0 | 64 nd | 0.00 | 0 |
| | **routed composition** | **57** | **5** | 2 nd | 1.02 | 3 |
| **F3** graph bottleneck -> allocation (n = 30) | graph alone: min-cut greedy (**best constituent**) | 19 | 0 | 11 sub | 0.20 | 1 |
| | optimiser alone on a flow-blind model | 0 | 0 | 30 sub | 0.55 | 1 |
| | **routed composition** (compile -> CP-SAT -> max-flow cross-check) | **30** | 0 | 0 | 1.05 | 3 |
| **F4** Bayes -> VOI -> next-best test (n = 30) | Bayes alone (never pilots) | 14 | 16 | 0 | 0.20 | 1 |
| | VOI on an uninformed prior (**best constituent**) | 18 | 12 | 0 | 0.40 | 2 |
| | **routed composition** | **30** | **0** | 0 | 0.60 | 3 |

Lift by family:

- **F2R:** 13 wins, 4 losses, p = 0.025. LIFT; wrong answers fell from 16 to 5.
- **F3:** 11 wins, 0 losses, p = 0.0005. LIFT.
- **F4:** 12 wins, 0 losses, p = 0.0002. LIFT.

**F5, NATURAL / independently derived.** Real M4 Weekly Micro/Industry series serve as product demand, with 30 held-out groups of three. Each arm stocks four weeks under a shared capacity and is scored on the realised cost on the real M4 test weeks:

| Arm | total realised cost | infeasible | median s | stages |
|---|---:|---:|---:|---:|
| forecasting alone (critical-ratio quantile, scaled to capacity) | 20 097 | 0 | 0.64 | 3 |
| optimiser alone on the last observed value (**best constituent**) | 16 725 | 0 | 0.76 | 2 |
| historical-mean plan | 27 130 | 0 | 0.00 | 0 |
| ablation: point forecast -> optimiser | 18 297 | 0 | 3.65 | 11 |
| **routed composition** (predictive distribution -> SAA -> CP-SAT) | **15 299** | 0 | 3.71 | 11 |
| hindsight optimum (unattainable reference) | 7 145 | | | |

F5 verdict under the frozen rule: **NOT LIFT**. Routed composition cut total realised cost by **8.5%** against the best constituent (mean 47.5 per group, median 24.8). It still won only 17 groups and lost 13 (p = 0.29), short of the per-group sign test. The ablation is informative: point forecasts plus the optimiser did worse than the optimiser alone, so the advantage that did appear came from the predictive distribution, not from forecasting the mean.

**VPL v2 = 3 of 4 families.**

Across v1 and v2, four materially distinct constructed geometries show lift:

- estimate -> optimise (F1, v1);
- identify -> optimise (F2R, replicating v1's underpowered F2);
- graph bottleneck -> allocation (F3);
- Bayes -> VOI -> next test (F4).

The one natural, independently derived family (F5) is directionally positive but not significant. Routing beat the fixed recipe everywhere: static composition answered only F5.

## Negative evidence and caveats

- **F4: correct under the model, worse in the world.** Composition took the Bayes-optimal action under the stated Beta(1, 1) posterior on all 30 items. Measured against the generator's true rates (drawn uniformly from 0.02-0.30, not from that prior), its mean realised value was -55, worse than the uninformed-VOI constituent's -20. The VPL rule scores decision correctness under the declared model, as pre-registered. This is the directive's point that a proof holds for the model, not for reality: a misspecified prior makes the "correct" decision lose money. It should become a calibration check (prior vs observed outcomes) before any such composition informs a real decision.
- **F2R failures.** Two items abstained at an identification stage (`F2R-27`, `F2R-41`); the association constituent got both right. Five items were wrong (`F2R-37`, `-59`, `-62`, `-83`, `-87`). Three of those were also wrong for the association constituent; on `-37` and `-87` the composition was wrong where association was right. Stratified estimates on 400 rows are noisy at the budget's integer margin, the same failure mode as v1 F2-21.
- **F5 is not significant.** Weeks within a group share a forecast, so the group is the sign-test unit; 30 groups were not enough at this effect size. The rule is not re-run on these groups.
- **Constructed families.** F2R, F3 and F4 are built to need two intelligences. They show that GREG's composition delivers the complementary answer with fewer false answers than any constituent; they do not show that founder tasks need composition. F5 is the first natural test.
- **F4 generator.** It was rebalanced before any arm ran. The first draft made "pilot" optimal on only 2 of 30 items, which left no power; recalibration used seeds 100-199, which belong to neither dev nor held out.
- **Cost.** No model calls and $0. Composition costs 3-11 isolated stages and about 0.4-3 s more latency than the best constituent, all well inside the 60 s budget.
