# Held-out genome admission, run 2026-10-14-v2

**What this is:** a re-admission of ten families on fresh held-out seeds. Every number below is copied from `results.json` by script; nothing was re-run, re-scored or re-labelled.

**Why it ran:** version-bound evidence (`bb65d6f`) made a status bind the genome version it was measured at. Six admitted genomes changed code in the independent-review fixes (`4d99fb0`), so their 2026-10-13-v1 statuses no longer bound their current versions; the Competency Compiler routes such genomes as UNEVALUATED until re-admitted. Two further families joined them:

- `decision_preposterior` and `newsvendor_compile` (composition stages whose code also changed);
- `collective_market`, under the amended oracle rule (below);
- `basal_bayes_filter`, a new Layer 1 genome (`1ac299b`).

## Protocol

| Item | Value |
|---|---|
| Freeze | `freeze.json`, committed in `8e37cd8` before any held-out instance was generated. It hashes the import closure of the harness and the isolated worker (106 code files), the M4 data, the requirement files and the dependency versions |
| Run | once, in a clean worktree at `8e37cd8`, pinned to one CPU core (as v1); `run.log` is its console output (exit 0) |
| Held-out seeds | 1100-1129, recorded in the freeze. Freezing refuses seeds spent by an earlier admission (v1's 1000-1029), development seeds 0-9 and P8's reserved 7000-8059 |
| Arms | candidate `solve` (an output refuted by the genome's independent verifier is scored wrong), simple baseline, strongest declared competitor |
| Statistics | paired one-sided exact sign tests, alpha 0.05; latency is wall-clock median in this container |
| Smoke | one held-out instance per genome through `greg.cognition.cortex.reason`, the family attached in an evaluation-only registry view |

Rule (verbatim from `results.json`):

> COMPOSITION_ONLY if no standalone decision; REJECTED if more wrong than baseline or significantly worse than baseline; EXPERIMENTAL if no significant edge over baseline (nor equal quality at >=1.25x lower median latency); SUPERSEDED if competitor significantly better and candidate wins none, or all ties and competitor >=1.25x cheaper; NICHE_CAPABILITY if beats baseline but significantly worse than competitor with some wins, or more wrong than competitor, or ties competitor at >=1.25x cost; DEFAULT_FOR_GEOMETRY if beats baseline, not significantly worse than competitor, no more wrong, and significantly better or <=1.25x competitor median latency. A competitor declared non-deployable (an oracle upper bound) is a reported reference: it neither supersedes nor demotes, so a candidate that beats its baseline without more wrong answers is DEFAULT_FOR_GEOMETRY. One-sided exact sign tests, alpha 0.05, 30 held-out seeds recorded in the freeze.

**The oracle clause is a disclosed rule amendment.** It was added in `c29e539` after v1 showed that an oracle competitor (the full-information optimum for `collective_market`) made a geometry unroutable: no deployable method can beat information it never sees. It was pre-registered before v2's seeds were generated and applies only forward. v1's evidence and its SUPERSEDED verdict for `collective_market` are unchanged in `../2026-10-13-v1/`. `collective_market`'s DEFAULT status here rests on that amendment: it beats its baseline 29-0 and ties the full-information optimum on all 30 instances.

## Results (scripted from `results.json`)

- **Source commit:** `8e37cd8`; freeze `sha256:05a965e1d2c31a5d...`; Linux-6.18.44-fc-v114-x86_64-with-glibc2.39, Python 3.13.16; finished 2026-10-14T00:45:19.260907+00:00.

| Layer | Genome | Version | Status | Cand c/w/a | Base wrong | Comp wrong | vs baseline | vs competitor | ms cand / comp | Smoke |
|---|---|---|---|---|---|---|---|---|---|---|
| L1 | `basal_bayes_filter` | 1.0.0 | **DEFAULT_FOR_GEOMETRY** | 30/0/0 | 16 | 0 | 20-0 (p=1e-06) | 14-2 (p_worse=1) | 61.79 / 1.16 | STRUCTURALLY_VERIFIED |
| L1 | `basal_pid` | 1.0.2 | **SUPERSEDED** | 30/0/0 | 0 | 0 | 30-0 (p=0) | 0-30 (p_worse=0) | 1.24 / 114.05 | STRUCTURALLY_VERIFIED |
| L2 | `collective_market` | 1.1.0 | **DEFAULT_FOR_GEOMETRY** | 30/0/0 | 0 | 0 | 29-0 (p=0) | 0-0 (p_worse=1) | 0.17 / 0.04 | STRUCTURALLY_VERIFIED |
| L3 | `causal_backdoor` | 1.2.0 | **DEFAULT_FOR_GEOMETRY** | 18/0/12 | 30 | 0 | 30-0 (p=0) | 8-4 (p_worse=0.927) | 1.03 / 1.45 | STRUCTURALLY_VERIFIED |
| L3 | `decision_preposterior` | 1.0.2 | **COMPOSITION_ONLY** | 30/0/0 | 0 | 0 | 30-0 (p=0) | 30-0 (p_worse=1) | 0.08 / 0.00 | STRUCTURALLY_VERIFIED |
| L3 | `forecast_quantile` | 1.1.0 | **DEFAULT_FOR_GEOMETRY** | 30/0/0 | 0 | 0 | 22-8 (p=0.00806) | 15-15 (p_worse=0.572) | 12.36 / 66.29 | STRUCTURALLY_VERIFIED |
| L3 | `newsvendor_compile` | 1.0.2 | **COMPOSITION_ONLY** | 30/0/0 | 0 | 0 | 30-0 (p=0) | 30-0 (p_worse=1) | 0.07 / 0.00 | STRUCTURALLY_VERIFIED |
| L3 | `queue_erlang` | 1.0.3 | **DEFAULT_FOR_GEOMETRY** | 30/0/0 | 29 | 4 | 29-0 (p=0) | 4-0 (p_worse=1) | 0.01 / 0.05 | STRUCTURALLY_VERIFIED |
| L4 | `develop_constraint_release` | 1.1.1 | **NICHE_CAPABILITY** | 30/0/0 | 0 | 0 | 22-3 (p=7.8e-05) | 5-15 (p_worse=0.0207) | 70.38 / 57.28 | STRUCTURALLY_VERIFIED |
| L4 | `develop_repair` | 1.1.1 | **NICHE_CAPABILITY** | 30/0/0 | 0 | 5 | 30-0 (p=0) | 7-23 (p_worse=0.00261) | 26.85 / 0.93 | STRUCTURALLY_VERIFIED |

Against the earlier run (v1 numbers from its `results.json`):

| Genome | v1 version | v1 status | v1 vs competitor | v2 version | v2 status | v2 vs competitor | refuted outputs v1 / v2 |
|---|---|---|---|---|---|---|---|
| `basal_bayes_filter` | - | not in v1 | - | 1.0.0 | DEFAULT_FOR_GEOMETRY | 14-2 | - / 0 |
| `basal_pid` | 1.0.1 | NICHE_CAPABILITY | 2-28 (p_worse=0) | 1.0.2 | SUPERSEDED | 0-30 (p_worse=0) | 0 / 0 |
| `causal_backdoor` | 1.1.0 | DEFAULT_FOR_GEOMETRY | 7-5 (p_worse=0.806) | 1.2.0 | DEFAULT_FOR_GEOMETRY | 8-4 (p_worse=0.927) | 0 / 0 |
| `collective_market` | 1.1.0 | SUPERSEDED | 0-0 (p_worse=1) | 1.1.0 | DEFAULT_FOR_GEOMETRY | 0-0 (p_worse=1) | 0 / 0 |
| `decision_preposterior` | 1.0.1 | COMPOSITION_ONLY | 30-0 (p_worse=1) | 1.0.2 | COMPOSITION_ONLY | 30-0 (p_worse=1) | 0 / 0 |
| `develop_constraint_release` | 1.1.0 | DEFAULT_FOR_GEOMETRY | 8-13 (p_worse=0.192) | 1.1.1 | NICHE_CAPABILITY | 5-15 (p_worse=0.0207) | 0 / 0 |
| `develop_repair` | 1.1.0 | NICHE_CAPABILITY | 12-18 (p_worse=0.181) | 1.1.1 | NICHE_CAPABILITY | 7-23 (p_worse=0.00261) | 0 / 0 |
| `forecast_quantile` | 1.0.1 | DEFAULT_FOR_GEOMETRY | 19-11 (p_worse=0.951) | 1.1.0 | DEFAULT_FOR_GEOMETRY | 15-15 (p_worse=0.572) | 0 / 0 |
| `newsvendor_compile` | 1.0.1 | COMPOSITION_ONLY | 30-0 (p_worse=1) | 1.0.2 | COMPOSITION_ONLY | 30-0 (p_worse=1) | 0 / 0 |
| `queue_erlang` | 1.0.2 | DEFAULT_FOR_GEOMETRY | 5-0 (p_worse=1) | 1.0.3 | DEFAULT_FOR_GEOMETRY | 4-0 (p_worse=1) | 0 / 0 |

Native subregions against the competitor (reported in receipts, never a status):

| Genome | Subregion | n | wins-losses-ties | p_better | p_worse |
|---|---|---:|---|---:|---:|
| `basal_bayes_filter` | high_noise | 16 | 13-1-2 | 0.000916 | 1 |
| `basal_bayes_filter` | low_noise | 14 | 1-1-12 | 0.75 | 0.75 |
| `basal_pid` | balanced | 10 | 0-10-0 | 1 | 0.000977 |
| `basal_pid` | delay_dominant | 8 | 0-8-0 | 1 | 0.00391 |
| `basal_pid` | lag_dominant | 12 | 0-12-0 | 1 | 0.000244 |
| `causal_backdoor` | continuous_covariates | 15 | 8-4-3 | 0.194 | 0.927 |
| `causal_backdoor` | discrete_covariates | 6 | 0-0-6 | 1 | 1 |
| `causal_backdoor` | latent_nodes | 9 | 0-0-9 | 1 | 1 |
| `collective_market` | oversubscribed | 29 | 0-0-29 | 1 | 1 |
| `collective_market` | slack | 1 | 0-0-1 | 1 | 1 |
| `develop_constraint_release` | loose_due_dates | 16 | 1-7-8 | 0.996 | 0.0352 |
| `develop_constraint_release` | tight_due_dates | 14 | 4-8-2 | 0.927 | 0.194 |
| `develop_repair` | reliable_controller | 15 | 0-15-0 | 1 | 3.1e-05 |
| `develop_repair` | unreliable_controller | 15 | 7-8-0 | 0.696 | 0.5 |
| `queue_erlang` | load_10_100 | 13 | 2-0-11 | 0.25 | 1 |
| `queue_erlang` | load_over_100 | 9 | 0-0-9 | 1 | 1 |
| `queue_erlang` | load_under_10 | 8 | 2-0-6 | 0.25 | 1 |

## What changed, and why

- **No verifier refuted any candidate output in either run** (last column of the comparison). Neither status change comes from a verifier rejecting valid answers.
- **`basal_pid` moved from NICHE to SUPERSEDED.** It lost 28 of 30 instances to the simulation-optimised PI in v1, and all 30 here. The rule separates NICHE from SUPERSEDED by "some wins", so two v1 wins were the whole difference. It is now excluded from routing. A control-tuning request that only `basal_pid` fits returns CAPABILITY_DEFICIT, routed to Capability Genesis. At this run's commit the deficit receipt does not yet name the superseding method, although that method is a deployable competitor already in the genome module.
- **`develop_constraint_release` moved from DEFAULT to NICHE.** Against random-restart search with the same budget it went from 8-13 (p_worse = 0.19, not significant) to 5-15 (p_worse = 0.021). On fresh seeds the loss became significant. Its v1 DEFAULT was not robust. It stays usable as a niche method; within the loose-due-dates subregion it lost 1-7.
- **`develop_repair` stayed NICHE but lost more decisively** (12-18 to 7-23). Its reliable-controller subregion lost 0-15; the unreliable-controller subregion, the geometry it was built for, split 7-8.
- **`forecast_quantile` stayed DEFAULT;** its edge over the Theta competitor shrank from 19-11 to 15-15. DEFAULT needs only "not significantly worse" and a latency condition. It is 5x faster.
- **`causal_backdoor`, `queue_erlang`, `decision_preposterior` and `newsvendor_compile` replicated their statuses.**
- **`basal_bayes_filter` (new) is DEFAULT.** It beats the admitted Schmitt-trigger genome 13-1 under high noise and ties it under low noise (1-1-12). It is about 50x slower (61.8 ms against 1.2 ms), which DEFAULT allows only because it is significantly better overall (14-2).

## Replication finding (negative evidence about the admission rule itself)

Eight families were re-measured under an unchanged rule. Six kept their status; two moved one rung down, and both had sat at a rule boundary in v1. A thirty-seed status near a boundary is a sample, not a property. The index now keeps every run's status per genome (`history`), so a status that changed between independent held-out runs is visible to routing and to the founder. The rule is frozen and is not changed by this observation. A future rule version that requires replication for DEFAULT would have to be pre-registered before its seeds are generated.

## Totals after this run

The evidence index takes each genome's latest frozen status. After this run, all 32 executable genomes have evidence measured at their current version, and none is routed on stale evidence:

- 13 DEFAULT_FOR_GEOMETRY, 8 NICHE_CAPABILITY, 6 SUPERSEDED, 3 COMPOSITION_ONLY, 2 EXPERIMENTAL, 0 REJECTED;
- admitted (DEFAULT or NICHE): 21 (L1 5, L2 3, L3 11, L4 2).

None is attached. Attaching any genome on the body is the founder's decision; the compiler prepares the ask.

## Reproduce

```
git worktree add /tmp/admit-v2 8e37cd8 && cd /tmp/admit-v2
PYTHONPATH=. taskset -c 0 python -m greg.cognition.genomes.admission --run 2026-10-14-v2
```

The harness refuses with `FROZEN_INPUT_CHANGED` if any frozen input differs, and refuses to overwrite `results.json`.

## Erratum (2026-10-14, after an independent review of the run)

These corrections change no number in `results.json` and no status the frozen rule assigned. They correct what the statuses can be taken to mean.

- **`forecast_quantile`'s held-out data were not fresh.** The genome draws `pool[(seed * 7919) % 241]` from a finite pool of 241 M4 weekly series. Seeds 1100-1129 are new numbers, and their series are distinct from the development seeds and from v1. But all 30 were in P8's forecasting cycle (2026-10-08), as training or held-out series: that cycle split all 201 series left after development and v1. The P8 candidate was rejected and nothing it learned entered the genome, so the genome was not fitted to these series. Still, "never generated" (the pre-registration commit `8e37cd8`) is true of the seed numbers only, not of the data. Read `forecast_quantile`'s v2 DEFAULT as a replication on data already used elsewhere in the project. Its edge over the Theta competitor was 15-15, so DEFAULT here rests on latency. Independent evidence on genuinely fresh data is P6 v3 (F6, real bank arrivals): staffing to its q* quantiles covered 0.675 / 0.911 / 0.966 of blocks against nominal 0.667 / 0.900 / 0.967.
- **The harness now refuses this** (`209f72c`). The freeze compares data identities (`instance_key`) with development seeds, earlier admissions and completed P8 cycles. P8 splits exclude every admission's series. No unused weekly series remains, so a further forecast admission needs new data.
- **"All 32 genomes carry evidence at their current version" held at this run's commit only.** `basal_bayes_filter` became 1.0.1 in `d05c1dc`: a stricter verifier and an abstention at a one-sample dwell, the solver unchanged otherwise. Its DEFAULT, measured at 1.0.0, is stale until re-admitted. The compiler routes it as UNEVALUATED and says so.
- **The "11-1 under high noise" in the genome's declaration** (`1ac299b`) misquoted v1: that was the HMM competitor's 11-1 against the Schmitt genome overall. This run measured 13-1-2 under high noise, which the declaration now cites.
