# Held-out genome admission, run 2026-10-13-v1

**What this is:** the first held-out admission of GREG's executable IntelligenceGenome library (31 genomes,
L1 x5, L2 x6, L3 x18, L4 x2) under the pre-registered rule in `greg/cognition/genomes/admission.py`.
Every number below is copied from `results.json` by script; nothing was re-run, re-scored or re-labelled.

## Protocol

| Item | Value |
|---|---|
| Freeze | `freeze.json`, committed in `496c85b` before any held-out instance ran (`freeze_sha256` sha256:9eb502ac9325e1e0...) |
| Run | once, in a clean worktree at `496c85b`, pinned to one CPU core; `run.log` is its console output |
| Held-out seeds | 1000-1029 (30 per genome), never generated before this run |
| Arms | candidate `solve` (output refuted by the genome's independent verifier is scored wrong), simple baseline, strongest declared competitor |
| Statistics | paired one-sided exact sign tests, alpha 0.05; latency is wall-clock median in this container |
| Smoke | one held-out instance per genome through `greg.cognition.cortex.reason` with the family attached in an evaluation-only registry view |
| Platform | Linux-6.18.44-fc-v114-x86_64-with-glibc2.39, Python 3.13.16 |

Rule (verbatim): COMPOSITION_ONLY if no standalone decision; REJECTED if more wrong than baseline or significantly worse than baseline; EXPERIMENTAL if no significant edge over baseline (nor equal quality at >=1.25x lower median latency); SUPERSEDED if competitor significantly better and candidate wins none, or all ties and competitor >=1.25x cheaper; NICHE_CAPABILITY if beats baseline but significantly worse than competitor with some wins, or more wrong than competitor, or ties competitor at >=1.25x cost; DEFAULT_FOR_GEOMETRY if beats baseline, not significantly worse than competitor, no more wrong, and significantly better or <=1.25x competitor median latency. One-sided exact sign tests, alpha 0.05, 30 held-out seeds.

## Results

Columns: candidate correct/wrong/abstain; wrong answers of the baseline and competitor; candidate wins-losses
against each other arm (ties omitted); median latency candidate / competitor in milliseconds.

| Layer | Genome | Status | Cand c/w/a | Base wrong | Comp wrong | vs baseline | vs competitor | ms cand / comp | Smoke |
|---|---|---|---|---|---|---|---|---|---|
| L1 | `basal_bandit` | **DEFAULT_FOR_GEOMETRY** | 30/0/0 | 3 | 0 | 28-2 (p=0) | 21-8 (p_worse=0.996) | 8.35 / 43.75 | STRUCTURALLY_VERIFIED |
| L1 | `basal_breaker` | **NICHE_CAPABILITY** | 30/0/0 | 0 | 0 | 30-0 (p=0) | 16-14 (p_worse=0.708) | 1.01 / 0.46 | STRUCTURALLY_VERIFIED |
| L1 | `basal_hysteresis` | **NICHE_CAPABILITY** | 30/0/0 | 12 | 0 | 13-0 (p=0.000122) | 1-11 (p_worse=0.00317) | 1.06 / 57.11 | STRUCTURALLY_VERIFIED |
| L1 | `basal_kalman` | **DEFAULT_FOR_GEOMETRY** | 30/0/0 | 2 | 0 | 30-0 (p=0) | 29-1 (p_worse=1) | 0.14 / 3.87 | STRUCTURALLY_VERIFIED |
| L1 | `basal_pid` | **NICHE_CAPABILITY** | 30/0/0 | 0 | 0 | 30-0 (p=0) | 2-28 (p_worse=0) | 1.27 / 119.13 | STRUCTURALLY_VERIFIED |
| L2 | `collective_aco` | **DEFAULT_FOR_GEOMETRY** | 30/0/0 | 0 | 0 | 30-0 (p=0) | 0-0 (p_worse=1) | 134.89 / 1496.21 | STRUCTURALLY_VERIFIED |
| L2 | `collective_flock` | **SUPERSEDED** | 19/0/11 | 30 | 0 | 30-0 (p=0) | 0-30 (p_worse=0) | 26.85 / 952.94 | SMOKE_FAILED |
| L2 | `collective_immune` | **EXPERIMENTAL** | 30/0/0 | 3 | 0 | 19-10 (p=0.068) | 5-25 (p_worse=0.000162) | 202.81 / 1.52 | STRUCTURALLY_VERIFIED |
| L2 | `collective_market` | **SUPERSEDED** | 30/0/0 | 0 | 0 | 25-0 (p=0) | 0-0 (p_worse=1) | 0.11 / 0.04 | STRUCTURALLY_VERIFIED |
| L2 | `collective_physarum` | **NICHE_CAPABILITY** | 30/0/0 | 0 | 0 | 20-4 (p=0.000772) | 2-12 (p_worse=0.00647) | 40.94 / 14.94 | STRUCTURALLY_VERIFIED |
| L2 | `collective_quorum` | **EXPERIMENTAL** | 29/1/0 | 2 | 4 | 2-0 (p=0.25) | 3-0 (p_worse=1) | 0.11 / 0.03 | STRUCTURALLY_VERIFIED |
| L3 | `bayes_interval` | **NICHE_CAPABILITY** | 27/3/0 | 9 | 3 | 20-10 (p=0.0494) | 18-12 (p_worse=0.9) | 0.28 / 0.00 | STRUCTURALLY_VERIFIED |
| L3 | `causal_backdoor` | **DEFAULT_FOR_GEOMETRY** | 18/0/12 | 29 | 0 | 30-0 (p=0) | 7-5 (p_worse=0.806) | 0.81 / 1.27 | STRUCTURALLY_VERIFIED |
| L3 | `control_mpc` | **DEFAULT_FOR_GEOMETRY** | 30/0/0 | 0 | 0 | 27-3 (p=4e-06) | 27-0 (p_worse=1) | 45.70 / 0.97 | STRUCTURALLY_VERIFIED |
| L3 | `decision_preposterior` | **COMPOSITION_ONLY** | 30/0/0 | 0 | 0 | 30-0 (p=0) | 30-0 (p_worse=1) | 0.07 / 0.00 | STRUCTURALLY_VERIFIED |
| L3 | `dp_knapsack` | **SUPERSEDED** | 30/0/0 | 23 | 0 | 23-0 (p=0) | 0-0 (p_worse=1) | 0.33 / 0.14 | STRUCTURALLY_VERIFIED |
| L3 | `flow_capacity_plan` | **COMPOSITION_ONLY** | 30/0/0 | 0 | 0 | 30-0 (p=0) | 30-0 (p_worse=1) | 0.09 / 0.00 | STRUCTURALLY_VERIFIED |
| L3 | `flow_maxflow` | **DEFAULT_FOR_GEOMETRY** | 30/0/0 | 14 | 0 | 14-0 (p=6.1e-05) | 0-0 (p_worse=1) | 1.67 / 2.60 | STRUCTURALLY_VERIFIED |
| L3 | `flow_reinforce_greedy` | **SUPERSEDED** | 16/14/0 | 30 | 0 | 30-0 (p=0) | 0-14 (p_worse=6.1e-05) | 0.81 / 2.80 | STRUCTURALLY_VERIFIED |
| L3 | `forecast_quantile` | **DEFAULT_FOR_GEOMETRY** | 30/0/0 | 0 | 0 | 20-10 (p=0.0494) | 19-11 (p_worse=0.951) | 10.43 / 54.05 | STRUCTURALLY_VERIFIED |
| L3 | `game_minimax` | **SUPERSEDED** | 30/0/0 | 19 | 0 | 19-0 (p=2e-06) | 0-0 (p_worse=1) | 3.66 / 1.80 | STRUCTURALLY_VERIFIED |
| L3 | `info_experiment` | **NICHE_CAPABILITY** | 30/0/0 | 0 | 0 | 30-0 (p=0) | 5-23 (p_worse=0.000456) | 7.37 / 43.61 | STRUCTURALLY_VERIFIED |
| L3 | `mc_importance` | **NICHE_CAPABILITY** | 30/0/0 | 2 | 0 | 30-0 (p=0) | 3-26 (p_worse=8e-06) | 0.28 / 0.01 | STRUCTURALLY_VERIFIED |
| L3 | `mech_vcg` | **DEFAULT_FOR_GEOMETRY** | 30/0/0 | 0 | 0 | 12-0 (p=0.000244) | 16-0 (p_worse=1) | 0.09 / 0.02 | STRUCTURALLY_VERIFIED |
| L3 | `newsvendor_compile` | **COMPOSITION_ONLY** | 30/0/0 | 0 | 0 | 30-0 (p=0) | 30-0 (p_worse=1) | 0.06 / 0.00 | STRUCTURALLY_VERIFIED |
| L3 | `queue_erlang` | **DEFAULT_FOR_GEOMETRY** | 30/0/0 | 24 | 5 | 24-0 (p=0) | 5-0 (p_worse=1) | 0.01 / 0.04 | STRUCTURALLY_VERIFIED |
| L3 | `search_astar` | **SUPERSEDED** | 30/0/0 | 29 | 0 | 29-0 (p=0) | 0-0 (p_worse=1) | 1.15 / 0.70 | STRUCTURALLY_VERIFIED |
| L3 | `synth_cegis` | **DEFAULT_FOR_GEOMETRY** | 30/0/0 | 13 | 0 | 13-0 (p=0.000122) | 0-0 (p_worse=1) | 14.95 / 30.43 | STRUCTURALLY_VERIFIED |
| L3 | `verify_modelcheck` | **DEFAULT_FOR_GEOMETRY** | 24/0/6 | 21 | 9 | 21-3 (p=0.000139) | 21-3 (p_worse=1) | 1.05 / 209.01 | STRUCTURALLY_VERIFIED |
| L4 | `develop_constraint_release` | **DEFAULT_FOR_GEOMETRY** | 30/0/0 | 0 | 0 | 25-1 (p=0) | 8-13 (p_worse=0.192) | 53.98 / 47.86 | STRUCTURALLY_VERIFIED |
| L4 | `develop_repair` | **NICHE_CAPABILITY** | 30/0/0 | 0 | 5 | 30-0 (p=0) | 12-18 (p_worse=0.181) | 28.96 / 0.90 | STRUCTURALLY_VERIFIED |

Totals: DEFAULT_FOR_GEOMETRY 12, NICHE_CAPABILITY 8, SUPERSEDED 6, COMPOSITION_ONLY 3, EXPERIMENTAL 2, REJECTED 0.

## Negative evidence and caveats (kept, not explained away)

- **Superseded by a mature or simpler mechanism (6):** `collective_market`, `game_minimax` (HiGHS LP),
  `dp_knapsack` (OR-Tools) and `search_astar` (SciPy Dijkstra) tie their competitors on every instance while
  the competitor is at least 1.25x faster; `collective_flock` (centralised prioritised planning, 0-30) and
  `flow_reinforce_greedy` (exact composition, 0-14, 14 non-optimal plans) lose outright. They stay registered
  as fallbacks and counterfactual twins.
- **No demonstrated edge over the simple baseline (2):** `collective_immune` (19-10 vs a z-score baseline,
  p=0.068; the exact prediction region beats it 25-5) and `collective_quorum` (2-0 with 28 ties).
- **Wrong answers:** `bayes_interval` 3 (a 90% interval missing the generating parameter; the competitor
  misses the same 3), `collective_quorum` 1, `flow_reinforce_greedy` 14. No other candidate gave a wrong answer.
- **Borderline DEFAULTs, by the letter of the rule:**
  - `develop_constraint_release` is DEFAULT although random restart wins more instances (13-8, not significant,
    p_worse 0.19) at similar latency.
  - `forecast_quantile` beats the naive Gaussian at p=0.0494, just under alpha.
  - `causal_backdoor` ties doubly robust AIPW 7-5 with 18 ties.
  Each would need a larger held-out set to move.
- **Latency-decided statuses on sub-millisecond medians are noisy:** for example, `bayes_interval` is NICHE
  rather than DEFAULT because the SciPy competitor answers in 0.003 ms against 0.28 ms.
- **Dev-seed statuses (not evidence) differed for several genomes**, for example `basal_pid` (SUPERSEDED on dev,
  NICHE held out: 2-28) and `verify_modelcheck` (EXPERIMENTAL on dev, DEFAULT held out). Ten dev seeds are
  for building, not admission.
- **Canonical-path defect found by the smoke:** `collective_flock` abstained on seed 1000, and the cortex
  raised `CognitionError: proof artifact requires its bounded output` instead of returning an abstention
  receipt. Its status is SUPERSEDED regardless (a failed smoke can only demote DEFAULT). The defect is in
  `greg/cognition/cortex.py`, outside the frozen inputs, and is fixed in a later commit with a regression test.
  This run's record stays as measured.

## What this does and does not show

- It shows **native competence per genome on its own problem family**, against a stated baseline and the
  strongest competitor the builder could name, on unseen instances.
- It does **not** show Verified Polyintelligence Lift: VPL is measured on composition families
  (`docs/evidence/greg-composition-lift/`). It does not attach any family: every genome stays registered
  VERIFIED (withheld), and attaching one is the founder's decision.
- **Authority delta: none.** Read-only computations; no model calls; no external effects.

## Erratum: independent evidence review, 2026-10-13

An independent read-only review (a separate agent, not the one that built and ran this admission)
re-derived every status from the per-instance rows and checked every claim. The evidence itself
holds:
- `results.json` is unedited;
- all 11 freeze hashes match `496c85b` and every later commit;
- all 31 statuses re-derive exactly;
- every table cell above matches `results.json`.

The prose above overstated or misdescribed seven points. It is kept as written; the corrections
follow.

1. **"Admitted" means DEFAULT_FOR_GEOMETRY or NICHE_CAPABILITY.** The admitted count is 20 of the
   31 evaluated: L1 5, L2 2, L3 11, L4 2. The other 11 are not admitted:
   - 6 SUPERSEDED and 3 COMPOSITION_ONLY, which the compiler excludes;
   - 2 EXPERIMENTAL.

   Layer 2 is thin: 4 of its 6 genomes are SUPERSEDED or EXPERIMENTAL.
2. **"Superseded by a mature or simpler mechanism" fits at most 4 of the 6:** `game_minimax`,
   `dp_knapsack`, `search_astar` and `flow_reinforce_greedy`.
   - `collective_market`'s competitor is a centralized optimum that knows every private value. That
     is an upper bound using information no market has, not a deployable mechanism; its SUPERSEDED
     status comes from a 0.07 ms latency gap on 30 ties.
   - `collective_flock`'s competitor is stronger but about 35x slower, so it is not simpler.

   Consequence, recorded rather than re-ruled: the compiler excludes SUPERSEDED, so the market
   geometry has no routable method. The next admission version should not let a competitor that
   uses unavailable information supersede.
3. **SUPERSEDED genomes are not "fallbacks."** They stay registered and VERIFIED (withheld), but
   `compiler.candidates()` rejects them, so no fallback routing exists.
4. **`develop_repair` does not simply "lose" to the replanner.** Overall it is 12-18, and p_worse =
   0.18 is not significant.
   - With a reliable controller it loses 0-15.
   - With an unreliable controller it wins 12-3 (p = 0.018).
   - The replanner gave 5 wrong answers and the candidate gave 0.

   Its NICHE status comes from latency, not quality. The subregion result is reported, not part of
   the rule.
5. **`bayes_interval`'s competitor is not SciPy.** It is the closed-form Wilson interval from the
   standard library; the SciPy dependency belongs to the candidate (Jeffreys).
6. **The narrative is hand-written; the table is scripted.** "Every number below is copied from
   results.json by script" is true of the table only.
7. **"p=0" means p < 1e-6.** The table shows `round(p, 6)`; for example, 28-2 is about 4.3e-7.

The freeze also left code unhashed that the run depends on:
- `greg/cognition/cortex.py`, through the smoke;
- `greg/cognition/solvers.py`;
- `developmental/mica.py` and `developmental/contracts.py`;
- the M4 data.

None changed between `496c85b` and `7f491c5`, so this run is unaffected. Admission freezes now hash
the computed import closure and the dependency versions (`cortex/evaluation/closure.py`, commit
`4d99fb0`).
