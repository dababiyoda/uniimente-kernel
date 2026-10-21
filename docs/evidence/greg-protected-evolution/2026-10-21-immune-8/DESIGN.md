# immune-8 pilot declaration (step C, 2026-10-21)

**Status:** declared and committed **before any instance of review seeds 4000-4999 was generated.** Executable form: `scripts/p8_immune8_pilot.py` below its step-C marker. `tests/unit/test_p8_immune8_pilot.py` checks this file against the code.

Context: `LINEAGE.md` (step A, causal reason) and `EXPOSURE-AUDIT.md` (step B, data).

This pilot is design knowledge only. It is not evidence for any cycle, and it decides nothing about adoption.

## 1. Search space

- **Name:** `immune-8/alarm-cap/1`, in `evolution.IMMUNE_SEARCH_SPACES` and `evolution.immune_search_space`.
- **Change:** `alarm_fraction` is limited to **[0.4, 0.75]**. 0.75 is the incumbent's own value; the full space allows [0.4, 0.95].
- **Every other axis is unchanged:** detectors, uniform share, scale set, calibration folds and whitening.
- **Left alone:** the genome's `IMMUNE_CONFIG_SPACE`, its incumbent `IMMUNE_DEFAULT_CONFIG` (`cfg-68b55c07dbdc`) and `evolution.immune_target()`'s default.
- **Where it is used:** `immune_target("immune-8/alarm-cap/1")` builds the space, and only this pilot uses it. No target spec uses it.

## 2. Data

| Use | Seeds | Items |
|---|---|---|
| Train T1 / T2 / T3 | 4000-4119 / 4120-4239 / 4240-4359 | 120 each |
| Look pool (held-out resampling) | 4360-4999 | 640 |

`guard` refuses every other seed, except development seeds 0-9, which only tests use. It also refuses every seed step B found exposed or reserved:

- admission seeds 1000-1029, 1100-1129 and 1200-1399;
- 3000-3999;
- 5001-5040;
- P8 7000-9199;
- every spent admission seed.

Instances come from `collective.immune_gaussian_instance`, the generator P8 cycles draw from.

## 3. Search procedures (both simulated)

Each runs on each train set, with 120 train items:

| Procedure | Settings |
|---|---|
| `mutate-incumbent/1` | generations 5, population 8 |
| `cover/1` | lhs 0, so the axis cover of the narrowed space, plus the same search |

- **Search seed:** 20261022, for the pilot only. A recorded cycle takes a fresh seed.
- **Runs:** 6 simulated cycles.
- **Train size is fixed at 120.** It is not varied, because a smaller train set would mean smaller stress sets, and smaller stress sets would make the wrong-answer gate easier to pass by sampling less.
- **Candidate selection is unchanged:** lowest train mean loss (`run_search`; any train violation makes a configuration's mean +inf).

Each simulated cycle applies the cycle's own steps:

1. the trigger: the incumbent is worse than z-score on at least 25% of train items;
2. the train-gain gate: more than 1%;
3. the adversarial gate;
4. a held-out step, resampled from the pool with replacement, 2,000 draws per size: the one-sided sign test p is below the threshold and the candidate's mean loss is lower. Any wrong answer makes a mean +inf, and +inf is never lower.

## 4. Gate implementation

The adversarial gate is the one merged from the independent stress-gate audit (`09555108`, merged at `180cd32`):

- `evolution.stress_summary(incumbent_losses, candidate_losses)` runs on **item-level** losses: items are grouped by exact kind and paired by key, and malformed values are marked;
- `evolution.stress_worsened` is applied to each kind and fails closed;
- `evolution.outputs_verified` checks the candidate's stress answers.

These are the same calls `evolution.cycle` makes. Means-only gating is not used anywhere in this pilot.

## 5. Comparators

| Comparator | Role |
|---|---|
| incumbent `cfg-68b55c07dbdc` | the rule's reference |
| `zscore`: `collective.immune_zscore` | the rule's trigger baseline |
| `hotelling`: `collective.immune_prediction_region` | the exact Gaussian prediction ellipsoid. This is the strongest simple detector on this regime and admission's declared competitor; admission v1 had the genome losing to it 5-25 |
| `knn5`: `collective.immune_knn_conformal` | a nonparametric simple detector |

These fixed configurations are labelled **INFORMED BY PRIOR OBSERVATIONS**. They come from immune-7's region rows (review seeds 3460-3999) and cycle 2's lineage. They are comparators only, never candidates.

| Label | Inside the narrowed space |
|---|---|
| `informed:whitening-full` | yes |
| `informed:full-scale1-u0.511 (cycle-2 rank 4)` | yes |
| `informed:full-scale1-u0.492` | yes |
| `informed:full-scale1-u0.511-a0.789 (cycle-2 rank 3)` | no |
| `informed:cycle-2 REJECTED candidate (a0.866)` | no |

Each informed configuration is measured three ways:

- on the pool: paired against the incumbent and every baseline;
- under the merged gate on each train set's stress items;
- as a "fixed-config protocol" P(RETAIN): the resampled held-out rate times the fraction of train sets whose gate it passes.

## 6. Resource limits and stopping

| Mode | Wall-clock limit | Evaluation limit |
|---|---|---|
| region | 3,600 s | 15,000 |
| simulate | 3 x 3,600 s | 50,000 |

- **Cores:** 2-3 (`taskset -c 2,3`), two worker processes.
- **Checking:** limits are checked before every configuration evaluation. Exceeding one stops the mode, and the record says so.
- **Every declared run happens exactly once.** There are no extra runs, no other search seeds, no seed extension, no re-run with a larger budget, and no change to the rules after looking.

## 7. Viability criterion and choice (`choose`)

**INCOMPLETE is NOT_VIABLE.** A declared limit that stops the pilot early means it never qualifies.

**VIABLE** requires both:

- the trigger fires on at least 2 of the 3 train sets;
- some cell (search procedure, held-out size n) has a mean simulated P(RETAIN) at alpha 0.05 of **at least 0.30**, under the unchanged `RULE` with the merged gate.

**n** is taken from **120, 240, 360, 480**:

- P(RETAIN) is reported as a function of n, at 0.05, at 0.05/2 (the second cycle on this target) and at 0.05/7 (the seventh P8 cycle).
- **The chosen n is the LARGEST n with a viable cell.** A smaller held-out size is never chosen to hide rare errors.

**The chosen procedure** is the one with the highest mean P(RETAIN) at 0.05/7 at that n. Ties go to `mutate-incumbent/1`.

## 8. Error accounting

Every configuration and baseline reports, on the pool, on train and on each stress kind:

- wrong answers (false-alarm violations) as a count out of n;
- the exact one-sided 95% Clopper-Pearson upper bound on the rate.

**What a RETAIN would imply.** Under the rule, RETAIN requires the candidate to make **zero** violations on the held-out split. Zero observed violations in n items bounds the rate at 1 - 0.05^(1/n): 2.5% at 120, 1.24% at 240, 0.83% at 360 and 0.62% at 480. Zero observed errors never means zero risk.

## 9. Multiple attempts

- **This pilot:** the second design pilot on `immune_detect`. A cycle it qualified would be the second recorded cycle on this target and the seventh P8 cycle overall.
- **Thresholds:** the rule decides at 0.05. Results are reported beside 0.025 and 0.05/7 = 0.00714.
- **If NOT_VIABLE:** this lane proposes **no third immune pilot**. The negative result is kept, and work moves to the second-target survey. There is no redesign-and-retest loop toward RETAIN.

## 10. Confirmatory split (proposal only; nothing generated)

If VIABLE, a draft pre-registration proposes:

- train: 120 seeds from 8840-8959;
- held out: n seeds from the remaining free P8-reserved seeds. Those are 8960-9199 and then 7040-7199 (step B lists 720 free seeds).

Immune-7's 8600-8839 stay unused.
