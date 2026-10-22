# P6 v3 composition lift: a natural call-centre family, 2026-10-14

- **Runner:** `cortex/evaluation/composition_lift/run_v3.py`.
- **Suite:** `cortex/evaluation/composition_lift/suite-v3.json`, 14 development days (60-73) and 90 held-out days (74-163).
- **Freeze:** `cortex/evaluation/composition_lift/freeze-v3.json`, committed in `5acda2c` before any held-out arm ran. The freeze hashes the computed import closure of the runner and the isolated worker: 111 files, including all of `greg/cognition`, `greg/capabilities.py` and the sandbox filter `tools/offline_test.py`. v1 and v2 hashed a hand-picked list that left modules on the path unhashed. Their runs are still pinned by `source_commit`, because each ran in a clean worktree at its freeze commit.
- **Run:** a clean worktree at `5acda2c`, three processes, each pinned to one core (`--workers 3`). Each day runs whole on one process, so latency is per core.
- **Path:** every arm runs through `greg.cognition.cortex.reason`, with isolated workers and an independent verifier per stage. `cognition.forecast_quantile` and `cognition.queue_erlang` are attached in an evaluation-only registry view; on the body they stay registered and withheld.

## Why F6

v2 measured VPL 3 of 4. Its one natural family, F5 (real M4 weekly demand -> newsvendor under a shared capacity), was 8.5% cheaper than the best constituent but not significant (17 wins, 13 losses, p = 0.29). Recomputed from `results-v2.json`, two causes are visible:

- The shared capacity bound the composed plan in **113 of 120** held-out weeks, and the optimiser-alone plan in 108. Realised demand exceeded capacity in 83 weeks. Whatever the forecast said, the plan was mostly the capacity, so composition had little room to differ.
- Thirty groups gave the sign test little power at that effect size.

F6 was chosen to remove both causes without choosing the answer:

- There is no shared capacity: each half-hour block is staffed separately.
- There are 90 held-out days.
- The geometry is a real two-intelligence problem. Forecasting supplies a predictive distribution of arrivals; queueing theory converts a rate into the agents needed to meet a service target. Neither does the other's job.

## Data and provenance

- **Source:** `bank_calls` from the fpp3 R package (Hyndman & Athanasopoulos, *Forecasting: Principles and Practice*, 3rd ed.). It holds the 5-minute call counts of a large North American commercial bank on 164 weekdays, 2003-03-03 to 2003-10-24, 07:00-21:00.
- **Download:** the Rdatasets CSV mirror (`https://raw.githubusercontent.com/vincentarelbundock/Rdatasets/master/csv/fpp3/bank_calls.csv`), sha256 `6e430180c3fa8a284e38b8367e9a7d6dae4921ca1b184cbaba7aae9b07a8f9a5`.
- **Committed file:** `cortex/evaluation/data/bank_calls_halfhour.json.gz`, sha256 `e2ec4cdae7888dbdbca01a5509cfd770fa2bbdf8d4fb16ed51261fcf8c2a8cdb`. It holds 28 half-hour totals per day; the single 21:00-21:05 interval is dropped.
- **Rebuild:** `python -I cortex/evaluation/data/build_bank_calls.py bank_calls.csv` rebuilds the file byte for byte (gzip mtime 0), and refuses any source with a different digest. Evaluation never downloads.
- **Licence (founder-reviewable item):** fpp3 is GPL-3. The file is factual counts, aggregated, for research. Whether redistributing a derived table in this repository is acceptable is Alfonso's decision; the build script can replace the committed file if not.

## Design, frozen before any held-out arm ran

- **Item:** one held-out day. The input is, for each of 28 half-hour blocks, the counts on every earlier day; the day being scored is never in the payload (tested).
- **Decision:** agents per block.
- **Cost per block:** `c * agents + P * max(0, required - agents)`, with c = 1 and the shortage penalty P in {3, 10, 30} rotated by day.
- **Requirement:** `required` is the Erlang C staffing at the **realised** arrival rate for P(wait > 20 s) <= 0.2 with a 240 s mean handle time. It is computed on the evaluation side by the SciPy Poisson path (`solvers_b.erlang_truth`), not by the genome being evaluated.
- **What is real:** the arrivals and outcomes. The handle time, service target and cost weights are a declared standard workforce-management decision layer. The queueing model is an assumption shared by every arm.
- **Composition (`forecast_then_staff`):** for each block, `forecast_distribution` gives the q* = 1 - c/P predictive quantile of the block's arrivals, then `erlang_c_staffing` staffs that rate. The Erlang requirement rises with the rate, so the q* quantile of the rate is the q* quantile of the requirement. That is the newsvendor-optimal staffing under the predictive distribution; a brute-force test checks it.
- **Constituents:**
  - `erlang_alone`: the queueing intelligence on the latest observed count. It has no predictive distribution of its own.
  - `forecast_alone`: the forecaster's q* quantile, staffed by an 85%-occupancy rule, as a forecaster without a queueing model would.
- **Ablations (reported, not in the rule):**
  - `median_forecast_then_staff`: isolates the value of the predictive quantile.
  - `weekly_mean_then_staff`: the mean of the last five weekdays -> Erlang C, the common practitioner pipeline.
- **Rule:** F6 counts toward VPL when routed composition meets all of the following:
  - it has no no-decision;
  - its total realised cost over 90 days is below the best constituent's;
  - it has no more infeasible plans than the best constituent;
  - it beats the best constituent on a one-sided exact sign test over days, p < 0.05;
  - its median latency is <= 120 s.

  The best constituent is chosen on the held-out results, which is conservative toward the constituents.
- **Declared limitation of the forecaster:** the admitted forecasting genome (damped Holt with empirical log-ratio error quantiles) lists "seasonality is not modelled" among its failure modes, and "strong seasonality" as a counterindication. Call arrivals by weekday may carry day-of-week effects. F6 uses the genome as admitted; nothing was adapted to these data.

## Results (scripted from `results-v3.json`)

- **Source commit:** `5acda2c`; manifest sha256 `af90173537c84af3...`; 3 pinned workers; Python 3.13.16.
- **Development selection:** static recipe `forecast_then_staff`.
- **Held-out days:** 90; hindsight-optimal cost (unattainable reference) 412,595.

| Arm | total realised cost | vs hindsight | infeasible | no decision | short blocks | agents short | agents paid | median s | stages |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Erlang C alone on the latest count (constituent) | 720,326 | 1.746x | 0 | 0 | 1223 | 20,569 | 412,742 | 6.842 | 28 |
| forecaster's q* quantile with an 85% occupancy rule (constituent) (**best constituent**) | 539,340 | 1.307x | 0 | 0 | 105 | 1,424 | 531,649 | 6.997 | 28 |
| ablation: median forecast -> Erlang C | 715,226 | 1.733x | 0 | 0 | 1192 | 21,236 | 405,719 | 13.841 | 56 |
| ablation: mean of the last five weekdays -> Erlang C | 662,089 | 1.605x | 0 | 0 | 1058 | 16,591 | 413,205 | 6.839 | 28 |
| static composition (recipe chosen on development days) | 506,301 | 1.227x | 0 | 0 | 377 | 5,786 | 473,393 | 13.938 | 56 |
| **routed composition** (q* forecast -> Erlang C) | 506,301 | 1.227x | 0 | 0 | 377 | 5,786 | 473,393 | 13.914 | 56 |

Routed composition against every other arm (one-sided; a win is a day with lower realised cost):

| Against | wins | losses | sign test p | Wilcoxon p | cost reduction |
|---|---:|---:|---:|---:|---:|
| Erlang C alone on the latest count (constituent) | 58 | 32 | 0.004023 | 0.000025 | 29.7% |
| forecaster's q* quantile with an 85% occupancy rule (constituent) | 74 | 16 | <1e-6 | <1e-6 | 6.1% |
| ablation: median forecast -> Erlang C | 49 | 41 | 0.230396 | 0.009041 | 29.2% |
| ablation: mean of the last five weekdays -> Erlang C | 40 | 50 | 0.876947 | 0.273738 | 23.5% |
| static composition (recipe chosen on development days) | 0 | 0 | 1.000000 | n/a | 0.0% |

**Verdict under the frozen rule: LIFT.** Best constituent `forecast_alone`; routed 74 wins, 16 losses, sign test p < 1e-6 (exact one-sided 2.2e-10; the runner stores six decimals, so the file reads 0.0); translation failures 0.0, composition failures 0.0; model calls 0, money $0.0.

**VPL v3 = 1 of 1 families.**

By shortage penalty (descriptive, not part of the rule):

| P | days | routed cost | best-constituent cost | weekly-mean cost | routed wins vs best |
|---:|---:|---:|---:|---:|---:|
| 3 | 30 | 155,067 | 161,899 | 153,756 | 21 |
| 10 | 30 | 172,180 | 184,534 | 189,972 | 28 |
| 30 | 30 | 179,054 | 192,907 | 318,361 | 25 |

## VPL tracking metrics (reported, never a verdict)

Computed by `python -I cortex/evaluation/composition_lift/vpl_metrics.py docs/evidence/greg-composition-lift/2026-10-14-v3/results-v3.json`, a reader added after the run that changes no evidence.

- **Cost delta against the best constituent:** -33,039 (-6.1%) over 90 paired days.
- **Latency delta:** +6.9 s median per day. Composition runs two verified stages per block (56 stages per day against 28).
- **False-answer delta 0, abstention delta 0.** No arm produced an infeasible plan or failed to decide.
- **Routing regret** (routed cost minus the cheapest arm on that day, ablations included): mean 400.9, total 36,084. Routing was regret-free on 24 of 90 days. The regret is mostly the weekly-mean ablation, which was cheaper on 50 days.
- **Calibration:** each row is the share of blocks staffed at or above the realised requirement, against the critical fractile q*. A newsvendor policy on a calibrated predictive distribution covers about q* of blocks. Each row covers 840 blocks.

| q* (P) | routed composition | forecast_alone |
|---|---:|---:|
| 0.667 (P = 3) | 0.675 | 0.904 |
| 0.900 (P = 10) | 0.911 | 0.975 |
| 0.967 (P = 30) | 0.966 | 0.996 |

Composition hits the fractile within about one point at every penalty. The forecaster alone over-staffs, because its 85%-occupancy rule converts a rate into agents without a queueing model. That over-staffing is the 6.1% it loses.

## What the result shows, and what it does not

- **VPL on natural families is now 1 of 2.** F5 (v2) did not lift and F6 (v3) did. VPL v3 is 1 of 1. The cumulative account in `docs/evidence/greg-mind-evidence-index.json` keeps every family's latest frozen verdict, F5's negative included.
- **The lift is composition, not routing.** The routed and static arms gave identical answers on all 90 days: the router chose `forecast_then_staff` every time, as development had. P4's demotion of conditional routing stands; this run neither revives nor contradicts it.
- **Composition does not beat the practitioner pipeline on day count.** Against the weekly-mean ablation it wins 40 days and loses 50 (p = 0.88). It is 23.5% cheaper in total only because the weekly mean collapses at P = 30 (318,361 against 179,054). At P = 3 the weekly mean is cheaper (153,756 against 155,067). A deployment decision would compare against that pipeline, not only against the single intelligences.
- **The value is in the predictive quantile.** The median-forecast ablation, which uses the same two genomes, is 29.2% more expensive in total. Its day count against composition is not significant (49-41, p = 0.23; Wilcoxon p = 0.009). Composing the forecaster's median with the queueing model is not the gain; composing its q* quantile is.
- **The decision layer is declared, not observed.** The 240 s handle time, the 20 s service target and the cost weights are a standard workforce-management layer, not the bank's. The arrivals and the realised requirement are real; the Erlang C model is an assumption shared by every arm.
- **One bank, consecutive weekdays, 2003.** Days are the unit of the sign test but are not independent draws from a population of call centres. The result supports "the composition works on this call stream", not "on call centres".
- **Version labels.** The run executed the post-review genome code at `5acda2c` under version strings `forecast_quantile` 1.0.1 and `queue_erlang` 1.0.2. `bb65d6f` relabelled the same code as 1.1.0 and 1.0.3 (in `greg/cognition/genomes/forecasting.py` and `solvers_b.py`, `git diff 5acda2c bb65d6f` changes only the three version strings), and admission v2 re-admits those versions on fresh seeds. This run is pinned by its source commit, not by the labels.
- **Licence.** Redistributing the fpp3-derived table is a founder decision (above).

## Reproduce

```
git worktree add /tmp/p6v3 5acda2c && cd /tmp/p6v3
PYTHONPATH=. python cortex/evaluation/composition_lift/run_v3.py --workers 3 --out results-v3.json
```

The runner refuses with `FROZEN_INPUT_CHANGED` if any of the 111 frozen files or the recorded dependency versions differ from `freeze-v3.json`. `run.log` is the run's own output (exit 0); `results-v3.json` is unedited, sha256 `35aa07f76b897ae3fcbbb2de9d0498cef5da779aa3c0a3e7e9e9e57628d6305a`.
