# Genome admission v8 (2026-10-22): 8 DEFAULT, 4 NICHE, 2 EXPERIMENTAL, 1 SUPERSEDED

- **Pre-registration:** [`PREREGISTRATION.md`](PREREGISTRATION.md), committed in `28e29538`. The exposure ledger that cites it is `3a0dce12`. Five lanes built the 15 genomes in parallel from #158 `c04b0f18`; their branches `claude/v8-lane-A` … `claude/v8-lane-E` are kept as lineage.
- **Freeze:** [`freeze.json`](freeze.json), committed in `bc966a18` before any held-out instance was generated.
- **Run:** once, from a clean detached worktree of `bc966a18`, under `taskset -c 1`. Load was 0.56 at the start and 1.00 at the end; wall time was 5 minutes. Outputs: [`results.json`](results.json) and [`run.log`](run.log).
- **Rule:** `RULE` verbatim, unchanged since v2. Held-out seeds 1700-1729.

## Generated from results.json (`scripts/admission_readme.py`)

- **Run:** source commit `bc966a18`, source dirty [], freeze `sha256:a4e1c766b0d03342…`, finished 2026-10-22T06:21:52.325846+00:00.
- **Host load:** start {'1m': 0.56, '5m': 1.23, '15m': 1.79, 'runnable': 1, 'entities': 105}, end {'1m': 1.0, '5m': 1.08, '15m': 1.57, 'runnable': 1, 'entities': 101} (diagnostic only).

| Family | Layer | Version | Status | Candidate correct/wrong/abstain | vs baseline W-L-T (p better) | vs competitor W-L-T (p better / p worse) | Median s (candidate / baseline / competitor) | Canonical path |
|---|---|---|---|---|---|---|---|---|
| `basal_cusum_detect` | 1 | 1.0.0 | **DEFAULT_FOR_GEOMETRY** | 28/2/0 | 17-5-8 (0.00845) | 1-5-24 (0.984375 / 0.109375) | 0.000228 / 0.000398 / 0.000214 | STRUCTURALLY_VERIFIED |
| `basal_hamming_correct` | 1 | 1.0.0 | **NICHE_CAPABILITY** | 5/25/0 | 27-2-1 (1e-06) | 1-7-22 (0.996094 / 0.035156) | 0.000406 / 5e-05 / 0.016115 | STRUCTURALLY_VERIFIED |
| `control_robust_tube` | 3 | 1.0.0 | **EXPERIMENTAL** | 19/0/11 | 15-8-7 (0.10502) | 8-12-10 (0.868412 / 0.251722) | 0.003172 / 0.002073 / 0.054978 | STRUCTURALLY_VERIFIED |
| `convex_qp_dual` | 3 | 1.0.0 | **NICHE_CAPABILITY** | 30/0/0 | 18-4-8 (0.002172) | 20-0-10 (1e-06 / 1.0) | 0.002402 / 0.021735 / 0.160157 | n/a |
| `develop_differentiate` | 4 | 1.0.0 | **DEFAULT_FOR_GEOMETRY** | 30/0/0 | 30-0-0 (0.0) | 20-8-2 (0.017849 / 0.99373) | 0.002959 / 0.001099 / 0.132597 | STRUCTURALLY_VERIFIED |
| `evo_novelty_search` | 3 | 1.0.0 | **DEFAULT_FOR_GEOMETRY** | 30/0/0 | 9-0-21 (0.001953) | 16-1-13 (0.000137 / 0.999992) | 0.35815 / 0.323918 / 0.138605 | STRUCTURALLY_VERIFIED |
| `forecast_judgment_pool` | 5 | 1.0.0 | **EXPERIMENTAL** | 30/0/0 | 14-16-0 (0.707668) | 16-14-0 (0.427768 / 0.707668) | 0.001242 / 0.000431 / 0.000472 | STRUCTURALLY_VERIFIED |
| `forecast_recalibration` | 3 | 1.0.0 | **NICHE_CAPABILITY** | 30/0/0 | 22-8-0 (0.008062) | 2-28-0 (1.0 / 0.0) | 0.000571 / 0.000131 / 0.00079 | STRUCTURALLY_VERIFIED |
| `forecast_scenarios` | 3 | 1.0.0 | **DEFAULT_FOR_GEOMETRY** | 30/0/0 | 23-7-0 (0.002611) | 29-1-0 (0.0 / 1.0) | 0.047918 / 0.000126 / 0.021749 | STRUCTURALLY_VERIFIED |
| `game_nash_bargaining` | 3 | 1.0.0 | **SUPERSEDED** | 30/0/0 | 15-0-15 (3.1e-05) | 0-0-30 (1.0 / 1.0) | 0.004792 / 3.4e-05 / 0.002356 | STRUCTURALLY_VERIFIED |
| `game_repeated_sustain` | 3 | 1.0.0 | **DEFAULT_FOR_GEOMETRY** | 28/0/2 | 28-1-1 (0.0) | 1-2-27 (0.875 / 0.5) | 0.005763 / 3.9e-05 / 0.02635 | STRUCTURALLY_VERIFIED |
| `game_stackelberg_commit` | 3 | 1.0.0 | **DEFAULT_FOR_GEOMETRY** | 30/0/0 | 16-0-14 (1.5e-05) | 0-0-30 (1.0 / 1.0) | 0.007949 / 0.000489 / 0.007685 | STRUCTURALLY_VERIFIED |
| `hyper_select_lowlevel` | 3 | 1.0.0 | **NICHE_CAPABILITY** | 30/0/0 | 15-0-15 (3.1e-05) | 7-4-19 (0.274414 / 0.886719) | 0.25881 / 0.001681 / 0.174144 | STRUCTURALLY_VERIFIED |
| `mdl_model_select` | 3 | 1.0.0 | **DEFAULT_FOR_GEOMETRY** | 29/1/0 | 30-0-0 (0.0) | 3-0-27 (0.125 / 1.0) | 0.001101 / 0.000367 / 0.00111 | STRUCTURALLY_VERIFIED |
| `prove_resolution` | 3 | 1.0.0 | **DEFAULT_FOR_GEOMETRY** | 30/0/0 | 22-0-8 (0.0) | 7-0-23 (0.007812 / 1.0) | 0.00151 / 0.000166 / 0.008775 | STRUCTURALLY_VERIFIED |

`basal_cusum_detect` by subregion: large_declared_shift_arl10000 (n=7): vs baseline 3-2-2, vs competitor 0-1-6; large_declared_shift_arl20000 (n=6): vs baseline 4-1-1, vs competitor 0-0-6; large_declared_shift_arl5000 (n=9): vs baseline 5-1-3, vs competitor 1-2-6; small_declared_shift_arl20000 (n=5): vs baseline 4-0-1, vs competitor 0-1-4; small_declared_shift_arl5000 (n=3): vs baseline 1-1-1, vs competitor 0-1-2.

`basal_hamming_correct` by subregion: hamming_15_11_clean (n=5): vs baseline 4-0-1, vs competitor 0-0-5; hamming_15_11_noisy (n=8): vs baseline 8-0-0, vs competitor 1-6-1; hamming_7_4_noisy (n=4): vs baseline 3-1-0, vs competitor 0-0-4; secded_16_11_noisy (n=3): vs baseline 3-0-0, vs competitor 0-1-2; secded_8_4_clean (n=3): vs baseline 2-1-0, vs competitor 0-0-3; secded_8_4_noisy (n=7): vs baseline 7-0-0, vs competitor 0-0-7.

`control_robust_tube` by subregion: marginal_heavy_disturbance (n=10): vs baseline 3-2-5, vs competitor 0-3-7; marginal_light_disturbance (n=3): vs baseline 0-1-2, vs competitor 0-1-2; stable_heavy_disturbance (n=6): vs baseline 3-3-0, vs competitor 3-3-0; stable_light_disturbance (n=4): vs baseline 4-0-0, vs competitor 2-1-1; unstable_heavy_disturbance (n=5): vs baseline 5-0-0, vs competitor 3-2-0; unstable_light_disturbance (n=2): vs baseline 0-2-0, vs competitor 0-2-0.

`convex_qp_dual` by subregion: ill_conditioned (n=16): vs baseline 10-4-2, vs competitor 8-0-8; many_constraints (n=8): vs baseline 7-0-1, vs competitor 8-0-0; well_conditioned (n=6): vs baseline 1-0-5, vs competitor 4-0-2.

`develop_differentiate` by subregion: high_diameter_r1 (n=5): vs baseline 5-0-0, vs competitor 5-0-0; low_diameter_r1 (n=10): vs baseline 10-0-0, vs competitor 6-2-2; low_diameter_r2 (n=15): vs baseline 15-0-0, vs competitor 9-6-0.

`evo_novelty_search` by subregion: deceptive (n=18): vs baseline 9-0-9, vs competitor 9-1-8; direct (n=12): vs baseline 0-0-12, vs competitor 7-0-5.

`forecast_judgment_pool` by subregion: high_agreement_long_record (n=5): vs baseline 2-3-0, vs competitor 2-3-0; high_agreement_short_record (n=5): vs baseline 2-3-0, vs competitor 2-3-0; low_agreement_long_record (n=14): vs baseline 8-6-0, vs competitor 9-5-0; low_agreement_short_record (n=6): vs baseline 2-4-0, vs competitor 3-3-0.

`forecast_recalibration` by subregion: long_record (n=18): vs baseline 17-1-0, vs competitor 1-17-0; short_record (n=12): vs baseline 5-7-0, vs competitor 1-11-0.

`forecast_scenarios` by subregion: jump_drift (n=15): vs baseline 10-5-0, vs competitor 15-0-0; regime_ar (n=15): vs baseline 13-2-0, vs competitor 14-1-0.

`game_nash_bargaining` by subregion: 2_players (n=16): vs baseline 5-0-11, vs competitor 0-0-16; 3_players (n=14): vs baseline 10-0-4, vs competitor 0-0-14.

`game_repeated_sustain` by subregion: mixed_punishment_only (n=11): vs baseline 10-0-1, vs competitor 0-1-10; pure_punishment_available (n=15): vs baseline 14-1-0, vs competitor 0-1-14; target_is_stage_nash (n=4): vs baseline 4-0-0, vs competitor 1-0-3.

`game_stackelberg_commit` by subregion: mixed_commitment_gain (n=16): vs baseline 16-0-0, vs competitor 0-0-16; pure_commitment_optimal (n=14): vs baseline 0-0-14, vs competitor 0-0-14.

`hyper_select_lowlevel` by subregion: mixed_sizes_large (n=7): vs baseline 0-0-7, vs competitor 0-0-7; mixed_sizes_medium (n=8): vs baseline 0-0-8, vs competitor 0-0-8; triplet_large (n=9): vs baseline 9-0-0, vs competitor 4-3-2; triplet_medium (n=6): vs baseline 6-0-0, vs competitor 3-1-2.

`mdl_model_select` by subregion: n_gt_40 (n=17): vs baseline 17-0-0, vs competitor 0-0-17; n_le_40 (n=13): vs baseline 13-0-0, vs competitor 3-0-10.

`prove_resolution` by subregion: horn_large (n=10): vs baseline 10-0-0, vs competitor 3-0-7; non_horn_large (n=10): vs baseline 10-0-0, vs competitor 2-0-8; small_le_18_atoms (n=10): vs baseline 2-0-8, vs competitor 2-0-8.

## Reading (written by hand; the verdicts above are the rule's, unedited)

**Admitted (12 of 15).** None is attached; attaching is the founder's decision. What each verdict rests on:

| Family | Verdict | What it rests on |
|---|---|---|
| `develop_differentiate` | DEFAULT | Beats the centralised greedy MIS on message rounds, 20-8. On the low-diameter radius-2 graphs it is only 9-6, as the lane predicted. Every pattern is correct; random roles were wrong 30/30. |
| `evo_novelty_search` | DEFAULT | Beats MAP-Elites on the same descriptor 16-1, with the wins on deceptive mazes. It is about 2.6× slower than MAP-Elites. The map is in the input, so breadth-first search dominates outright; BFS is the truth here, not a competitor. |
| `forecast_scenarios` | DEFAULT | Beats K plain Monte Carlo paths 29-1 and persistence 23-7 on energy score, about 2.2× slower than Monte Carlo. Unmeasured: k-medoids scenario clustering, which may be stronger. |
| `prove_resolution` | DEFAULT | Every win over Z3 (7-0) comes from the declared scoring, 1 for a correct verdict with an independently checked proof and 0.5 without one. **On verdicts alone, Z3 and the prover both decide 30/30; the prover is not a stronger decider.** This admits GREG's route to a checkable resolution proof, on ground clauses only. |
| `mdl_model_select` | DEFAULT | Ties BIC 3-0-27 at equal latency. The offset sensitivity documented on dev cost one wrong answer (29/1/0). |
| `game_repeated_sustain` | DEFAULT | Ties brute-force simulation 1-2-27 at about 1/4.6 of its latency. It abstains on 2 degenerate stage games. |
| `game_stackelberg_commit` | DEFAULT | Ties HiGHS multiple LPs 0-0-30, within the 1.25× latency allowance (1.03×). Its distinct output is an exact rational certificate, which the rule does not score. This is the competitor that replaced the lane's Nash-commitment arm at merge review. |
| `basal_cusum_detect` | DEFAULT | Beats the calibrated window test 17-5. Against Shiryaev–Roberts it is 1-5-24, not significantly worse (p = 0.11), so the rule admits it. **Shiryaev–Roberts is at least as good on this benchmark.** |
| `convex_qp_dual` | NICHE | 30/30 certified, and beats SciPy `trust-constr` 20-0. The rule's decision was DEFAULT, demoted to NICHE because the canonical-path smoke failed: held-out seed 1700's request exceeds GREG's 64 KiB cognitive-request limit. **A real integration defect.** The method is strong, but GREG cannot route dense QPs that large to it. Fixing it means a new version or a request-size policy, then re-admission; it is not repaired here. |
| `basal_hamming_correct` | NICHE | Beats no correction 27-2. It loses to the exhaustive Bayes decoder 1-7-22 (p = 0.035) on noisy (15,11) blocks, where Bayes flags what syndrome decoding miscorrects. It is about 40× faster. |
| `hyper_select_lowlevel` | NICHE | Beats first-fit decreasing 15-0, with gains only on triplet instances. Its edge over the random-selection hyper-heuristic is 7-4, not significant. Under the rule, NICHE comes from its being slower than that competitor (1.49×). So the UCB1 credit assignment is not shown to add anything. |
| `forecast_recalibration` | NICHE | **In substance this is superseded.** Platt scaling beats it 28-2 (p_worse ≈ 0). The rule labels "significantly worse than the competitor with some wins" NICHE rather than SUPERSEDED, and 2 wins meet that. The rule is unchanged; whether "some wins" should need a minimum is recorded as a policy question for the founder. Routing should not prefer it over Platt scaling. |

**Not admitted (3 of 15).**
- `control_robust_tube` is **EXPERIMENTAL**. It is never wrong (19 correct, 11 abstain), but it is not significantly better than nominal MPC (15-8), and the min-max competitor, which optimises the score's own worst-case cost, goes 12-8. The tube abstains above n × horizon 12, where vertex verification is capped.
- `forecast_judgment_pool` is **EXPERIMENTAL**. It went 14-16 against the simple mean and 16-14 against the median. The dev 7:3 did not replicate, and its extremization gains nothing measurable on these panels.
- `game_nash_bargaining` is **SUPERSEDED**. SciPy SLSQP ties it 0-0-30 and is about 2× faster. Its supporting-hyperplane certificate is not scored.

**Coverage closed.** Admission closes these directive items, previously ABSENT:
- differentiation;
- novelty search;
- scenario forecasts;
- theorem proving, as checkable resolution proofs on ground clauses;
- compression / minimum description;
- repeated games;
- credible commitment;
- local sensing, at signal level only, since GREG has no physical sensors;
- convex optimization, NICHE;
- local error correction, NICHE;
- hyperheuristics, NICHE.

These items are now BENCHMARKED, not ADMITTED:
- robust control;
- judgmental forecasting;
- bargaining models.

**Limits.** Every instance is mathematical or simulated, so no verdict here speaks to a natural workload. The changes made after dev results were seen are disclosed in the pre-registration.
