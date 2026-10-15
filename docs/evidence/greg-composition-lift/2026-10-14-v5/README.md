# P6 v5 composition lift: F8, a Layer 1 tracker composed with queueing on real NYC demand, 2026-10-14

**Verdict:** F8 meets its pre-registered rule: routed composition beats the best single intelligence on held-out data. It does **not** beat the simpler EWMA-quantile ablation on total cost. That loss, which the pre-registration predicted, comes entirely from the tracker's abstentions, which fall back to the standing plan.

**Scope:** this measures the #158 lineage's code at the freeze commit `202b932`. It does not measure the converged Mind of PR #179, where this freeze refuses (`FROZEN_INPUT_CHANGED`) by design.

## Provenance

- **Runner:** `cortex/evaluation/composition_lift/run_v5.py`.
- **Pre-registration:** `cortex/evaluation/composition_lift/prereg-v5.json`, built in `53082f4`, corrected after independent review in `3462d37` and `59a15ab`. It passes `vpl_metrics.validate_preregistration`.
  - The review found a structural daylight-saving gap on 2015-03-08 and untyped staffing errors; both were fixed from the calendar and code alone.
  - Three disclosures that understated those changes were corrected, before the suite was built.
  - Every development look and the held-out audit looks are disclosed in the pre-registration.
- **Suite:** `suite-v5.json` (`dad6347`): 558 development items (2015-01-29 to 02-28) and 2,196 held-out items (122 dates, 2015-03-01 to 06-30; 6 streams; 3 decision blocks).
- **Freeze:** `freeze-v5.json` (`202b932`), committed before any held-out arm ran. It hashes 126 code files (the runner's and the isolated worker's import closure), the suite, the pre-registration, the data and the dependency pins.
- **Run:** once, in a clean worktree at `202b932`. Three workers were pinned to cores 1-3 (`--workers 3 --cores 1,2,3`), with the machine otherwise idle at the start; review agents later shared core 0 only. It finished at 2026-10-14T22:48:30Z; `run.log` is the console output (exit 0).
- **Path:** every GREG arm runs through `greg.cognition.cortex.reason`, with isolated workers and independent verifiers. `cognition.basal_kalman` and `cognition.queue_erlang` are attached in an evaluation-only registry view; on the body nothing is attached. Practitioner arms and ablations run in process, so their latency is not comparable with the GREG arms'.
- **`development-v5.json`:** the builder's development run at `53082f4`. It is not part of any verdict. The review change left development calibration and every development item identical.

## Data and terms

- **Source:** NYC Taxi and Limousine Commission Uber trip records, January-June 2015, released under New York's Freedom of Information Law and published by FiveThirtyEight (`fivethirtyeight/uber-tlc-foil-response`).
- **Extract:** `cortex/evaluation/data/uber_nyc_2015_halfhour.json.gz` (sha256 `33e05dfa...`). It holds aggregated half-hour pickup counts for six streams: Manhattan, Brooklyn, Queens excluding the airports, the Bronx, JFK and LaGuardia. It is rebuilt byte for byte by `build_uber_nyc_2015.py`.
- **Terms (release blocker, founder decision):** the source repository states no licence; FiveThirtyEight's CC BY 4.0 notice covers only its separate data repository. The data are public records, aggregated to counts here and used for evaluation only, attributed to the NYC TLC and FiveThirtyEight. Redistribution beyond evaluation is Alfonso's decision. PR #179 lists this extract as a release blocker alongside SNDlib, M4 and fpp3.

## Design, frozen before any held-out arm ran

- **Item:** one (stream, date, decision block) at 08:00, 13:00 or 18:00, decided with 30 minutes' notice from today's counts so far.
- **Requirement:** the agents Erlang C needs at the realised rate. The service-time mean is 1,200 s, the wait target 120 s, P(wait > target) ≤ 0.2, and the block 1,800 s.
- **Cost:** agents plus P times the shortfall, with P in {3, 10, 30}.
- **Composition (`track_then_staff`):** the Kalman tracker (`cognition.basal_kalman`, admitted DEFAULT in v1) tracks the day's multiplier over a standing plan. Its q* = P/(1+P) quantile feeds Erlang C (`cognition.queue_erlang`, admitted DEFAULT).
- **Fallback:** when the tracker abstains (fewer than 3 usable measurements, or its own innovation (NIS) test refuses the declared noise model), the arm falls back to the standing plan, staffed by Erlang C. Every declining arm is costed at that fallback.
- **Rule** (verbatim from `results-v5.json`):

> F8 (natural, continuous cost, fallbacks costed): routed total realised cost < best constituent total, routed malformed plans <= best constituent malformed plans, one-sided exact sign test over held-out items p < 0.05, routed median latency <= 60 s and <= 5x the best constituent's median. Best constituent chosen on held-out results (lowest total realised cost). Per-date sign test, per-stream results, abstention rates, practitioner, ablation and compiled-arm comparisons reported, not part of the rule. VPL = families meeting their rule.

## Results (scripted from `results-v5.json`)

- **Source commit:** `202b932`; 3 pinned workers; Python 3.13.16.
- **Development selection:** static recipe `track_then_staff`, the only recipe that fits.
- **Held-out items:** 2,196.

| Arm | total realised cost | decided | fallback | wrong | median s |
|---|---:|---:|---:|---:|---:|
| tracker alone: Kalman multiplier, Erlang at the plan (constituent) (**best constituent**) | 717,879 | 1993 | 203 | 0 | 0.7351 |
| queue intelligence alone: Erlang C at the latest observed rate (constituent) | 1,511,368 | 2175 | 21 | 0 | 0.6892 |
| practitioner: standing plan, then Erlang (in process) | 958,782 | 2196 | 0 | 0 | 0.001 |
| practitioner: cumulative day ratio, then Erlang (in process) | 790,154 | 2196 | 0 | 0 | 0.0009 |
| practitioner: EWMA ratio, then Erlang (in process) | 731,732 | 2196 | 0 | 0 | 0.0007 |
| ablation: EWMA ratio + q* quantile, then Erlang (in process) | 626,736 | 2196 | 0 | 0 | 0.0007 |
| ablation: Kalman median (no quantile), then Erlang | 778,898 | 1993 | 203 | 0 | 1.4282 |
| static composition (recipe chosen on development items) | 656,324 | 1993 | 203 | 0 | 1.4278 |
| **routed composition** (track -> staff) | 656,324 | 1993 | 203 | 0 | 1.4263 |
| Competency Compiler (`{compile: ...}`) | 656,324 | 1993 | 203 | 0 | 1.4281 |
| hindsight optimum | 491,518 | | | | |

Routed composition against every other arm (exact sign test over items; cost reduction is the relative difference in total realised cost):

| Routed composition vs | wins | losses | one-sided p | cost reduction |
|---|---:|---:|---:|---:|
| kalman_alone | 1589 | 204 | 0.0 | 8.6% |
| erlang_alone | 1414 | 719 | 0.0 | 56.6% |
| standing_plan_then_staff | 1057 | 907 | 0.000385 | 31.6% |
| cumulative_ratio_then_staff | 970 | 1191 | 0.999999 | 16.9% |
| ewma_ratio_then_staff | 899 | 1249 | 1.0 | 10.3% |
| ewma_ratio_quantile_then_staff | 1327 | 546 | 0.0 | -4.7% |
| kalman_median_then_staff | 850 | 1140 | 1.0 | 15.7% |
| static_composition | 0 | 0 | 1.0 | 0.0% |
| compiled | 0 | 0 | 1.0 | 0.0% |

- **Rule:** met. Routed costs 656,324 against `kalman_alone`'s 717,879 (8.6% less); 1,589-204 items; 120-2 dates (per-date sign test); Wilcoxon one-sided p = 1.9e-217; latency ratio 1.94, within 5x and 60 s; no malformed plan.
- **VPL v5:** 1 of 1.

**Where the total-cost loss to the EWMA-quantile ablation comes from** (computed from the held-out rows):

| Items | count | routed composition | EWMA-quantile ablation | routed wins-losses |
|---|---:|---:|---:|---:|
| decided by the composition | 1,993 | 498,491 | 516,541 | 1,233-452 |
| tracker abstained (standing-plan fallback) | 203 | 157,833 | 110,195 | 94-94 |
| all | 2,196 | 656,324 | 626,736 | 1,327-546 |

Where it answers, the composition is 3.5% cheaper than the ablation. Its 203 fallbacks cost 47,638 more than the ablation on those items, which turns the total into a 4.7% loss. 118 of the fallbacks run no stage: fewer than 3 usable measurements, because the night blocks are planned below half the day's mean. They are LaGuardia 08:00 (107), JFK 08:00 (5), Manhattan 08:00 (4) and JFK 13:00 (2). The other 85 are refusals by the tracker itself (one stage ran), 55 of them at Manhattan 18:00. The run records the state `STAGE_ABSTAINED` and the number of stages run, not the refusal reason. The reading that these are NIS refusals rests on the development diagnosis.

Per stream:

| Stream | items | routed | kalman_alone | ewma_ratio_quantile | standing plan | routed vs best (W-L) | routed fallbacks |
|---|---:|---:|---:|---:|---:|---:|---:|
| Bronx | 366 | 14,463 | 14,893 | 14,435 | 24,956 | 227-45 | 3 |
| Brooklyn | 366 | 93,840 | 102,161 | 93,774 | 151,490 | 330-32 | 4 |
| JFK Airport | 366 | 18,053 | 18,598 | 16,459 | 32,481 | 214-59 | 25 |
| LaGuardia Airport | 366 | 22,409 | 22,969 | 19,254 | 35,601 | 185-31 | 109 |
| Manhattan | 366 | 468,638 | 517,198 | 443,115 | 651,998 | 298-8 | 60 |
| Queens (excluding JFK and LaGuardia) | 366 | 38,921 | 42,060 | 39,699 | 62,256 | 335-29 | 2 |

Coverage of the routed quantile on answered items:

| Coverage at q* (answered items) | routed | kalman_alone | ewma_ratio_quantile |
|---|---:|---:|---:|
| 0.667 | 0.7087 | 0.8062 | 0.7669 |
| 0.900 | 0.8972 | 0.9097 | 0.9375 |
| 0.967 | 0.9417 | 0.9444 | 0.9864 |

The routed arm over-covers at q* = 2/3 and under-covers at 29/30 (0.942 against 0.967). The EWMA-quantile ablation covers more at every level.

## Predictions (pre-registered) against outcomes

| Prediction | Outcome |
|---|---|
| Routed costs less in total than both constituents and wins the item sign test; informativeness weak (the constituents ignore either the plan or the queue) | **Confirmed:** 8.6% and 56.6% cheaper; 1,589-204 and 1,414-719 |
| A total-cost loss to `ewma_ratio_quantile_then_staff`, possibly with more item wins than losses | **Confirmed:** 4.7% dearer (development 20.3%); 1,327-546 items |
| Static and compiled arms identical to routed on every item | **Confirmed** (0-0 discordant) |
| About 10% of items fall back | **Confirmed:** 9.24% (203 of 2,196) |

## What this does and does not show

- **Layer 1 inside a composition lifts over the best single intelligence on real demand.** F8 is the first family in which a Layer 1 genome (`basal_kalman`) is a stage. It meets the pre-registered VPL rule, so natural families are now **3 of 4** (F6, F7, F8 lift; F5 does not).
- **It does not show that the Kalman tracker earns its complexity on these data.** A simpler EWMA tracker with the same quantile and the same Erlang stage costs 4.7% less in total, because it never abstains. As the pre-registration stated, the loss is the cost of the tracker's refusals under its own abstention contract. Where the Kalman tracker answers, it is better (3.5% cheaper, 1,233-452).
- **Practitioner pipelines: mixed.** The composition beats the standing-plan practitioner on both total cost (31.6%) and items (1,057-907, p = 0.0004). It is cheaper in total than the cumulative-ratio and EWMA-ratio practitioners (16.9% and 10.3%) but loses to each on item count (970-1,191 and 899-1,249). So against those two, the lift is concentrated in the expensive items, not spread across the typical one.
- **Routing adds nothing within the family:** only one recipe fits.
- **Two improvements are suggested by the data, not adopted:**
  - a better fallback than the standing plan when the tracker refuses (for example, the EWMA ratio);
  - recalibrating the tracker's noise for the airport streams.
  Either would need a fresh pre-registered freeze under a new path. Neither may be applied retroactively to this result.

## Limits

- The outcome is real (realised pickups), but the requirement comes from the Erlang C model at the realised rate, and the service time, wait target, cost weights, decision blocks and notice are a declared decision layer, not Uber's dispatch.
- Items share dates and streams, so the item sign test treats them as independent. The per-date test (120-2) is reported alongside.
- One city and one half-year (2015). Streams are boroughs and airports of one platform.
- Latency is this container's, under the load described above.
