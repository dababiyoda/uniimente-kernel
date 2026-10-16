# P8 cycle 5: pre-registration (DRAFT, 2026-10-16)

**Status:** draft for the session owner. No cycle-5 instance has been generated: the split below was checked by `cr_split_seeds`, which generates nothing, and the pilot used review seeds 3000-3999 only. `freeze.json` does not exist yet.

The session owner will:

1. Review this file.
2. Write the freeze with the command in *Procedure*.
3. Fill in the *Seals* and *Trusted code* rows from it.
4. Commit both.
5. Run the cycle once.

Nothing in this file is evidence that cycle 5 ran.

## Hypothesis

On fresh instances of `develop_constraint_release`'s benchmark family, a restart-heavy search configuration has lower loss than the incumbent configuration of version 1.2.0. Here restart-heavy means `p_restart` ≥ 0.75 in the unchanged `CR_CONFIG_SPACE`; the incumbent is `CR_DEFAULT_CONFIG`, with `p_restart` = 0. A cycle whose generation 1 also evaluates the declared axis cover of the closed space will select such a configuration and keep it under the unchanged rule.

The cycle tests the whole chain:

- the trigger fires;
- the search selects a candidate that beats the incumbent's train loss by more than 1%;
- the candidate passes the adversarial gate;
- it wins the one held-out look.

A REJECT record names the stage that failed.

## Disclosures

- **The design was informed by cycle 4's reported random-restart result.** The cycle-4 README and its errata 2 and 3 report three things:
  - random restart beat the incumbent on 53% of train items and had the lowest held-out mean loss;
  - cycle 4's search tried `p_restart` only at 0.064, 0.156 and 0.339;
  - nothing above 0.339 was tried.

  That record is why this cycle targets the restart region. Cycle 4's split (7400-7589) is not reused, and none of its instances were generated for this design.
- **A pilot on review seeds chose the search policy and the split sizes** (section *Pilot*). It never generated a P8-reserved, admission or spent instance. `scripts/p8_cr_pilot.py` refuses any other seed, and `tests/unit/test_p8_cr_pilot.py` checks that it does.
- **This is the third attempt on this target.** Cycle 3 (2026-10-14) was rejected at the adversarial gate. Cycle 4 (2026-10-15) was rejected at the held-out gate. See *Multiple attempts*.
- **What a restart-heavy configuration is.** With `p_restart` = 1.0 every child is a uniformly random pipeline, so the search becomes random restart with its own random stream.
  - The search's random draws then no longer depend on `mu`, `offspring`, `tournament` or the other three probabilities. The one exception is an evaluation budget below `mu` + `offspring`, which makes it abstain.
  - In the pilot, all 15 grid configurations with `p_restart` = 1.0 had identical mean losses on both halves.
  - The target's baseline, `constraint_release_random_restart`, is the same algorithm with another stream.
  - So a RETAIN of such a candidate would mean that the evolutionary operators lose to random sampling on this geometry. Admission already pointed that way: random restart won 15-5 in v2 and 13-10 in v3. It would still be an improvement of the shipped configuration, found and verified through the protected route.

## Pilot (design evidence; review seeds 3000-3999 only)

All numbers below are copied from the files in `pilot/`.

- The script is `scripts/p8_cr_pilot.py`. It computes every loss as the cycle does:
  - `SealedEvaluator.losses` over `constraint_release_score`;
  - on the output of `constraint_release_solve_with`, the sandbox's method, or of `constraint_release_random_restart`, the baseline;
  - stress sets from `_cr_stress`;
  - simulated searches through the cycle's own `run_search`.
- It runs in-process, without the sandbox, which only confines and does not change any output.
- It is not in the trusted closure.

### 1. Grid: pilot-train 3000-3059 and pilot-test 3060-3119 (`pilot/grid.json`)

There are 140 configurations:

- 102 grid points: `p_restart` ∈ {0, 0.25, 0.5, 0.75, 0.9, 1.0}, crossed with (`mu`, `offspring`) ∈ {(2,2), (4,4), (8,8), (2,8), (8,2)} and `tournament` ∈ {1, 2, 3}, plus the other three probabilities at their bounds;
- 38 more from cycle 4's lineage; its incumbent is also a grid point.

| | pilot-train (60) | pilot-test (60) |
|---|---|---|
| incumbent mean loss | 0.010796 | 0.007752 |
| random restart mean loss | 0.006399 | 0.006276 |
| random restart vs incumbent (W-L-T, one-sided sign p) | 29-14-17, p = 0.01577 | 34-12-14, p = 0.000821 |
| items where the incumbent loses to random restart (the trigger's rate) | 48.3% | 56.7% |

By `p_restart` level (grid points only; the mean over the level's configurations):

| `p_restart` | n | train mean loss | test mean loss | train W-L vs incumbent | test W-L vs incumbent | sign p < 0.05 on both halves | lower mean on both halves | pass the stress gate |
|---|---|---|---|---|---|---|---|---|
| 0.0 | 19 | 0.00953 | 0.00727 | 22.6-16.4 | 20.5-18.9 | 0 | 11 | 6 |
| 0.25 | 15 | 0.00704 | 0.00634 | 27.2-14.7 | 25.1-18.4 | 2 | 14 | 8 |
| 0.5 | 19 | 0.00707 | 0.00649 | 27.6-15.0 | 25.9-18.9 | 2 | 16 | 12 |
| 0.75 | 15 | 0.00815 | 0.00698 | 29.0-15.1 | 28.7-17.1 | 6 | 10 | 9 |
| 0.9 | 19 | 0.00609 | 0.00898 | 29.6-14.4 | 30.2-15.8 | 12 | 1 | 17 |
| 1.0 | 15 | 0.00569 | 0.00976 | 30.0-15.0 | 27.0-16.0 | 0 | 0 | 15 |

- **Nine of the 140 configurations meet both held-out conditions of the rule on both halves:** one-sided sign p < 0.05 and lower mean loss. Seven of the nine have `p_restart` ≥ 0.5, and five of those have `p_restart` = 0.75.
- **Train mean loss does not predict test mean loss across configurations.** The Spearman rank correlation over the 140 is −0.179 (`pilot/summary.json`). Selecting the lowest train mean loss, which is what the rule does, is mostly noise between nearby configurations. This is consistent with how cycles 3 and 4 failed.
- **Cycle 4's candidate (`cfg-afdb92cb42e7`) replicates its failure on review seeds.**
  - Train: 22-15 against the incumbent, mean 0.010337.
  - Test: 17-25, mean 0.010677 against 0.007752.
  - Lean stress: 0.015019 against 0.007944, so it would fail the stress gate here.

### 2. Fresh pool: 300 review seeds 3200-3499 (`pilot/region.json`)

The configurations were fixed from §1 before the pool was generated:

- the `p_restart` sweep at the incumbent's other settings;
- the nine that passed on both halves;
- the top five by pilot-train loss;
- cycle 4's candidate;
- the three candidates of the first simulation batch.

The pool also gives a resampled decision. It draws n held-out items with replacement 2000 times and reports how often the rule's held-out step would RETAIN: sign p < 0.05 and lower mean loss. The rate at the reading-only threshold 0.05/3 follows it after a slash. The ninth configuration that passed on both halves, `cfg-ef21c4300207`, is also the 0.75 sweep point.

| configuration | mean loss (incumbent 0.009236) | W-L-T | sign p | RETAIN rate, n = 90 | RETAIN rate, n = 180 |
|---|---|---|---|---|---|
| random restart (the baseline) | 0.006548 | 143-84-73 | 5.5e-05 | 0.638 / 0.452 | 0.904 / 0.795 |
| incumbent with `p_restart` 1.0 | 0.005626 | 137-90-73 | 0.001097 | 0.475 / 0.289 | 0.756 / 0.576 |
| incumbent with `p_restart` 0.9 | 0.007239 | 132-102-66 | 0.028878 | 0.241 / 0.130 | 0.399 / 0.230 |
| incumbent with `p_restart` 0.75 | 0.006895 | 133-89-78 | 0.001902 | 0.428 / 0.248 | 0.712 / 0.524 |
| incumbent with `p_restart` 0.5 | 0.00706 | 118-92-90 | 0.042127 | 0.208 / 0.100 | 0.365 / 0.194 |
| incumbent with `p_restart` 0.25 | 0.008096 | 114-99-87 | 0.168721 | 0.110 / 0.043 | 0.169 / 0.070 |
| the 9 that passed on both halves (range) | 0.006484-0.008066 | | 4.9e-05 to 0.008781 | 0.324-0.642 | 0.518-0.912 |
| cycle 4's candidate | 0.009892 | 99-103-98 | 0.637457 | 0.021 / 0.007 | 0.020 / 0.005 |

- **The headroom is real, and it sits in the restart-heavy region.** `p_restart` = 1.0 has 39% lower mean loss than the incumbent on 300 fresh items, and wins 137-90.
- **The pilot-test mean anomaly at `p_restart` ≥ 0.9 does not replicate.** It was a heavy-tailed sample of 60 items.
- **Held-out size is the largest lever on power.**
  - The incumbent with `p_restart` = 1.0 would be kept 47.5% of the time at n = 90 and 75.6% at n = 180.
  - Random restart itself would be kept 63.8% and 90.4% of the time.

### 3. Simulated cycles (`pilot/simulate-*.json`)

Each simulated cycle:

- runs `run_search` on a review train set;
- applies the trigger, the 1% train gain and the adversarial gate (both stress sets, every output verified);
- measures the selected candidate on the fresh pool 3200-3499 as in §2.

A first batch (`pilot/simulate-1-*.json`) ran four policies on pilot-train with pilot-test as the look. Its candidates entered §2. The table below covers the later batches.

Each cell gives the candidate's `p_restart`, then its pool RETAIN rate at n = 90 / n = 180. Every simulated cycle triggered and advanced. All but one passed the adversarial gate (both stress sets, every output verified).

Generations 5 and population 8 unless stated.

| search | 3000-3059 (60) | 3060-3119 (60) | 3120-3179 (60) | 3000-3119 (120) | 3500-3619 (120) | 3620-3739 (120) | mean RETAIN rate, n = 90 / 180 (at 0.0167) |
|---|---|---|---|---|---|---|---|
| mutate-incumbent/1, seed 20261008 (cycle 4's settings) | 0.339: 0.29 / 0.50 | 0.156: 0.07 / 0.09 | 0.0: 0.04 / 0.04 | 0.156: 0.18 / 0.31 | 0.064: 0.01 / 0.01 | 0.0: 0.05 / 0.05 (stress gate fails) | 0.106 / 0.167 (0.053 / 0.096) over 6 |
| cover/1, `lhs` 16 | 0.335: 0.16 / 0.28 | 0.374: 0.37 / 0.59 | 0.88: 0.47 / 0.78 | 0.758: 0.45 / 0.69 | not run | not run | 0.363 / 0.585 (0.224 / 0.438) over 4 |
| **cover/1, `lhs` 0 (this cycle)** | 1.0: 0.47 / 0.76 | 0.374: 0.37 / 0.59 | 1.0: 0.47 / 0.76 | 0.0: 0.14 / 0.21 | 0.954: 0.51 / 0.81 | 0.885: 0.47 / 0.76 | 0.407 / 0.645 (0.251 / 0.488) over 6 |
| cover/1, `lhs` 16, generations 1 | 1.0: 0.47 / 0.76 | 0.0: 0.01 / 0.01 | 0.88: 0.58 / 0.87 | not run | not run | not run | 0.356 / 0.544 (0.233 / 0.44) over 3 |

- **cover/1 reaches the region by construction.** The mutate-incumbent search never selected `p_restart` above 0.339 in six simulated cycles. Its mean RETAIN rate at n = 180 was 0.167.
- **cover/1 with `lhs` 0 had the highest mean** (0.645 at n = 180). With `lhs` 0 the cover is the 16 one-key extremes of the incumbent, `p_restart` = 1.0 among them, and it does not depend on the seed.
  - It evaluated 49-53 configurations, against 66-69 for `lhs` 16, so it is less exposed to selecting the luckiest of many.
  - Four of its six simulated cycles selected `p_restart` ≥ 0.75 (1.0, 1.0, 0.954, 0.885).
  - One selected 0.374 (0.59 at n = 180) and one selected 0.0 (0.21).
- **A larger train set did not help.** For `lhs` 0 the mean RETAIN rate at n = 180 was 0.699 over the three 60-item train sets and 0.592 over the three 120-item ones. Three runs each cannot separate them, so this cycle keeps the 60-item train size of cycles 3 and 4.
- **The held-out size is raised from 90 to 180.** By §2 and the table above, it is the change with the largest effect on the probability of keeping a real improvement. The task that commissioned this design suggested 90 held-out items (7700-7789); 180 is a design choice from this pilot.

## What is fixed

| Item | Value |
|---|---|
| Target | `constraint_release`: the search policy (`CR_DEFAULT_CONFIG`) of `develop_constraint_release` 1.2.0, pinned in `EVOLVABLE_CONFIG_PINS` |
| Closed space | `developmental.CR_CONFIG_SPACE`, unchanged since cycle 3; choices compared type-strictly |
| Split | named `cycle-5` in `CR_SPLITS`: train seeds 7600-7659 (60), held-out seeds 7700-7879 (180). Inside P8's reserved range and disjoint from every admission seed and spent seed, the immune target's seeds, and cycles 3 and 4's splits (`cr_split_seeds`). |
| Settings | generations 5, population 8, search seed 20261016, search policy **cover/1** with `lhs` 0. The freeze lists all 16 declared configurations; the cycle re-derives the list and refuses any difference. |
| Rule | **unchanged**, verbatim in `freeze.json` (`inputs.rule`): see *Rule* below. Constants: trigger 0.25, train gain 0.01, stress tolerance 0.05, alpha 0.05. |
| Seals | train `sha256:…`, held-out `sha256:…` (filled from `freeze.json` when the owner writes it) |
| Trusted code | the static import closure as frozen by `freeze()` (filled from `freeze.json`; schema `greg-protected-evolution-freeze/3`) |
| Run | once, by `python -m greg.cognition.evolution --freeze F --out O` (the clean room), at the commit that adds `freeze.json`, pinned to one CPU core |

The 16 declared configurations are the incumbent with one key moved. `cfg-12b387892289` is the restart-heavy anchor.

| id | change from the incumbent |
|---|---|
| `cfg-b52d5222e575` | `mu` 2 |
| `cfg-3c66dc174fef` | `mu` 3 |
| `cfg-89c3c37f5bf1` | `mu` 6 |
| `cfg-2d4a15cf9f87` | `mu` 8 |
| `cfg-931e3c4aa0b1` | `offspring` 2 |
| `cfg-562c6fdf85bc` | `offspring` 6 |
| `cfg-baaa4a7e37f0` | `offspring` 8 |
| `cfg-7f97cd51a64d` | `p_extra_mutation` 0.0 |
| `cfg-554aac1da8d1` | `p_extra_mutation` 0.9 |
| `cfg-e917d51bcb66` | `p_extra_mutation_recombined` 0.0 |
| `cfg-2fc7cf1e5b52` | `p_extra_mutation_recombined` 0.9 |
| `cfg-f3a9b4ccfd74` | `p_recombine` 0.0 |
| `cfg-642ff26b1db9` | `p_recombine` 0.9 |
| `cfg-12b387892289` | `p_restart` 1.0 |
| `cfg-62e29869efc3` | `tournament` 1 |
| `cfg-2a647542961b` | `tournament` 3 |

The setting's digest is `sha256:9fb959be04ffe7b1117169c427494abc9c1ca6a6d80bc032f81d26bece406605` (`contracts.digest` of `search_setting(cr_target(), "cover/1", seed=20261016, lhs=0)`).

## Rule (unchanged)

> trigger: incumbent worse than the simple baseline on >= 25% of train items; candidate advances if its train mean loss beats the incumbent's by > 1%; adversarial: every output verifies and no stress set worsens by > 5%; RETAIN iff on the held-out split the one-sided exact sign test over paired items gives p < 0.05 and the candidate's mean loss is lower; otherwise REJECT. Never applied automatically.

This is `evolution.RULE`, byte-identical to cycle 4's `freeze.json`. The selection is also unchanged: the candidate is the evaluated configuration with the lowest train mean loss, ties broken by id. The stress sets are unchanged too: a lean budget of 16, and validation cut to four cases.

## What changed in the trusted parent since cycle 4

Everything is in `greg/cognition/evolution.py`. No change reaches the candidate side, the sandbox, the evaluator or the rule.

- **The search moved out of `cycle()` into `run_search()`.** The default policy (`mutate-incumbent/1`) is the same search draw for draw. Replayed with each recorded configuration's recorded train loss, all four recorded cycles visit their recorded lineage in order and select their recorded candidate (`test_every_recorded_cycles_search_replays_from_its_record_through_run_search`).
- **`SEARCH_POLICIES` adds `cover/1`.** After the incumbent's mutants, from its own random stream, generation 1 also evaluates:
  - the incumbent with one key at a time moved to each bound of a float and to each other choice;
  - then a Latin hypercube of `lhs` points.

  The search's own stream is unchanged.
- **The freeze schema is `greg-protected-evolution-freeze/3`.**
  - `settings.search` records the policy and every configuration it declares.
  - The cycle re-derives the setting from its declared policy and seed and refuses a different list, policy, seed or extra key (`FROZEN_INPUT_CHANGED`).
  - `generations`, `population` and `seed` must be integers.
- **`cr_split_seeds(name)` checks a split without generating it.** `cr_split` calls it before any instance exists.
- **`CR_SPLITS["cycle-5"]` is added and `CR_CURRENT_SPLIT` is `"cycle-5"`.** Cycles 3 and 4 keep their named splits, so their seeds, seal code and rule are unchanged. `test_earlier_constraint_release_splits_and_the_seal_code_are_unchanged` checks this without generating their instances. The re-seal of cycle 3 from its instances is the existing `test_an_earlier_cycles_split_reproduces_its_frozen_evaluator_seals`.
- **`--write-freeze` takes `--generations`, `--population`, `--seed`, `--search` and `--lhs`.**

Every integrity mechanism of cycle 4 still applies:

- the committed freeze;
- the clean room;
- one held-out look, and spent splits refused;
- the parent checks confinement and the executed code against the freeze;
- type-strict configurations.

## Multiple attempts

This is the third pre-registered cycle on `constraint_release`, after cycles 3 and 4.

- **The frozen rule decides with alpha 0.05.** The rule is unchanged.
- **The README will report the held-out p-value beside the three-attempt Bonferroni threshold, 0.05/3 = 0.0167.** This continues cycle 4's pre-registration, which reported its p-value beside the two-attempt threshold 0.025 "for reading only".
- **A RETAIN with 0.0167 ≤ p < 0.05 will be reported as a RETAIN that does not survive the three-attempt correction.**
- **The README will also report the programme-wide threshold, 0.05/5 = 0.01.** This is the fifth P8 cycle overall, and section 31 item 7 concerns protected evolution as a whole. A RETAIN with p ≥ 0.01 will be reported as not surviving that correction either.
- **The pilot's resampled RETAIN rates at the corrected threshold are lower.** They are the second number in each cell of §2.

## Prediction (from the pilot; not part of the rule)

- **These predictions are optimistic, for three reasons** (independent critique, 2026-10-16):
  - the six simulation train sets overlap: 3000-3119 is the union of two of the others, and 3000-3059 is pilot-train, which shaped the grid;
  - the policy (`cover/1`, lhs 0) was chosen as the best of four on the same pool, 3200-3499, that measured its RETAIN rate;
  - the resampling treats the 300-item pool as the population.
- **The support for `p_restart` = 1.0 rests on the pool, not on both pilot halves.** On pilot-test, `p_restart` = 1.0 has a higher mean loss than the incumbent (0.009761 against 0.007752; wins 27-16, p = 0.063). None of the nine configurations that pass both halves has `p_restart` above 0.75. The "lower mean" condition is tail-sensitive: on the pool, the top 5 of 300 items carry 36% of the incumbent-minus-1.0 loss difference.
- **The trigger fires.** The incumbent lost to random restart on 36.7-56.7% of the items of each of the six review train sets; the threshold is 25%.
- **The candidate has `p_restart` ≥ 0.75.** Four of the six simulated cycles of this policy selected one.
- **P(RETAIN) is about 0.65** under the frozen rule (alpha 0.05), and about 0.49 at the reading-only threshold 0.0167. This is the mean over the six simulated cycles of this policy of the selected candidate's resampled rate at n = 180 on the fresh pool; the six ranged from 0.21 to 0.81.
- **At the corrected threshold a RETAIN is about as likely as not.** A REJECT would not by itself refute the headroom, which §2 measured.

## What KEEP (RETAIN) would mean

- **The record would carry a `PROPOSED_NOT_APPLIED` proposal:**
  - change `CR_DEFAULT_CONFIG` in `greg/cognition/genomes/developmental.py` from the incumbent to the candidate;
  - roll back to the incumbent (`cfg-111751096c0d`).
- **Nothing is applied.** Adoption is a reviewed change and the founder's decision.
- **Adoption would bump `develop_constraint_release`'s version and its pin in `EVOLVABLE_CONFIG_PINS`.** Admission v3's DEFAULT_FOR_GEOMETRY verdict would then route as stale until re-admission on fresh seeds.
- **The canary is the target's own:** "re-admit develop_constraint_release with the proposed configuration on fresh seeds before adoption; keep comparing with the incumbent and random restart after adoption".
- **Re-admission matters here.** A restart-heavy configuration makes the genome nearly its own admission competitor, random restart. At re-admission it would beat the original-pipeline baseline and could tie the competitor.
- **Section 31 item 7 would be met at the proposal level.** Protected evolution would have found an improvement of non-constitutional cognition and verified it on a held-out split it could not alter. Using the improvement still needs adoption.
- **The README will state whether the RETAIN survives 0.0167.**

## What REJECT would mean

The record names the gate that failed.

| Gate that fails | What it means |
|---|---|
| Trigger | No recurring failure on this split. Nothing searched. |
| Train gain | The search found nothing better than the incumbent by more than 1% on train. Against the pilot, this would suggest the split differs from the review family. |
| Adversarial gate | The candidate's train gain does not survive the lean budget or four-case validation, as in cycle 3. |
| Held-out | The selected candidate did not win the one look, as in cycle 4. The pilot's resampled rates say this can happen even to a configuration with a real advantage (roughly one time in four at n = 180 for `p_restart` = 1.0). |

In every case:

- section 31 item 7 stays unmet after five cycles and five REJECTs;
- nothing is applied;
- the cycle-5 held-out split is spent.

A further cycle on this target would be the fourth attempt (Bonferroni 0.0125). It would need its own fresh split and pre-registration. It should not re-run this design with a relaxed gate, because the rule and its tolerances are frozen.

## Procedure (session owner)

1. Commit this design: the code, the tests, the pilot and this file. Check that the tree is clean.
2. Write the freeze. This is the first time any cycle-5 instance is generated:

   ```
   PYTHONPATH=. taskset -c 1 python -m greg.cognition.evolution --target constraint_release \
     --write-freeze docs/evidence/greg-protected-evolution/2026-10-16-cr-5/freeze.json \
     --generations 5 --population 8 --seed 20261016 --search cover/1 --lhs 0
   ```
3. Copy the printed seals into *What is fixed*, then commit `freeze.json` and this file together.
4. Run once, from a clean tree at that commit:

   ```
   PYTHONPATH=. taskset -c 1 python -m greg.cognition.evolution --target constraint_release \
     --freeze docs/evidence/greg-protected-evolution/2026-10-16-cr-5/freeze.json \
     --out docs/evidence/greg-protected-evolution/2026-10-16-cr-5/cycle-cr-5.json
   ```
5. Commit the record and its console log unedited. Write the README from the record by script, and give the p-value beside 0.0167.
