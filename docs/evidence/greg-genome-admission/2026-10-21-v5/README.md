# Genome admission v5 (2026-10-21): 7 DEFAULT, 2 NICHE, 1 SUPERSEDED, 1 REJECTED

The table is generated from `results.json` by `scripts/admission_readme.py`. Nothing was re-run.

- **Pre-registration:** `PREREGISTRATION.md` was committed at `2046b744`. `freeze.json` (sha256 `be40c282…`) was
  committed at `b8061a21`, before any held-out instance was generated.
- **Run:** once, at `b8061a21`, in a clean detached worktree, pinned to core 2, with no other Python process on that
  core. Exit 0 (`run.log`).
- **Seeds:** held-out 1400-1429.
- **Run:** source commit `b8061a21`, source dirty [], freeze `sha256:be40c282039a8204…`, finished 2026-10-21T19:08:41.251534+00:00.
- **Host load:** start {'1m': 0.14, '5m': 0.05, '15m': 0.25, 'runnable': 1, 'entities': 106}, end {'1m': 1.0, '5m': 0.6, '15m': 0.45, 'runnable': 1, 'entities': 103} (diagnostic only).

| Family | Layer | Version | Status | Candidate correct/wrong/abstain | vs baseline W-L-T (p better) | vs competitor W-L-T (p better / p worse) | Median s (candidate / baseline / competitor) | Canonical path |
|---|---|---|---|---|---|---|---|---|
| `basal_nlms` | 1 | 1.0.0 | **NICHE_CAPABILITY** | 30/0/0 | 30-0-0 (0.0) | 10-20-0 (0.978613 / 0.049369) | 0.00271 / 0.001073 / 0.007719 | STRUCTURALLY_VERIFIED |
| `basal_token_bucket` | 1 | 1.0.0 | **DEFAULT_FOR_GEOMETRY** | 30/0/0 | 23-7-0 (0.002611) | 20-10-0 (0.049369 / 0.978613) | 0.000342 / 0.000146 / 0.001202 | STRUCTURALLY_VERIFIED |
| `binpack_cpsat` | 3 | 1.0.0 | **DEFAULT_FOR_GEOMETRY** | 29/0/1 | 19-1-10 (2e-05) | 1-1-28 (0.75 / 0.75) | 0.041921 / 4.4e-05 / 0.788225 | STRUCTURALLY_VERIFIED |
| `blackbox_multistart_lbfgsb` | 3 | 1.0.0 | **DEFAULT_FOR_GEOMETRY** | 30/0/0 | 18-0-12 (4e-06) | 7-15-8 (0.973761 / 0.0669) | 0.133712 / 0.002885 / 0.14471 | STRUCTURALLY_VERIFIED |
| `collective_auction` | 2 | 1.0.0 | **SUPERSEDED** | 30/0/0 | 26-0-4 (0.0) | 0-0-30 (1.0 / 1.0) | 0.030941 / 0.000499 / 0.000858 | STRUCTURALLY_VERIFIED |
| `community_louvain` | 3 | 1.0.0 | **DEFAULT_FOR_GEOMETRY** | 30/0/0 | 27-0-3 (0.0) | 28-0-2 (0.0 / 1.0) | 0.038323 / 0.004823 / 0.031484 | STRUCTURALLY_VERIFIED |
| `crowd_weighted_vote` | 2 | 1.0.0 | **DEFAULT_FOR_GEOMETRY** | 30/0/0 | 30-0-0 (0.0) | 26-2-2 (2e-06 / 1.0) | 0.003701 / 0.000656 / 0.111219 | STRUCTURALLY_VERIFIED |
| `develop_diffusion` | 4 | 1.0.0 | **REJECTED** | 27/3/0 | 15-15-0 (0.572232) | 9-20-1 (0.98794 / 0.030714) | 0.012344 / 0.000844 / 0.009646 | STRUCTURALLY_VERIFIED |
| `graph_node_cut_exact` | 3 | 1.0.0 | **DEFAULT_FOR_GEOMETRY** | 30/0/0 | 7-0-23 (0.007812) | 7-0-23 (0.007812 / 1.0) | 0.001107 / 0.000327 / 0.001618 | STRUCTURALLY_VERIFIED |
| `maxsat_cpsat` | 3 | 1.0.0 | **DEFAULT_FOR_GEOMETRY** | 30/0/0 | 25-0-5 (0.0) | 4-0-26 (0.0625 / 1.0) | 0.023888 / 0.001475 / 0.046615 | STRUCTURALLY_VERIFIED |
| `reconcile_qp` | 3 | 1.0.0 | **NICHE_CAPABILITY** | 30/0/0 | 26-0-4 (0.0) | 2-0-28 (0.25 / 1.0) | 0.00335 / 0.000117 / 0.001101 | STRUCTURALLY_VERIFIED |

`basal_nlms` by subregion: long_high_dim (n=9): vs baseline 9-0-0, vs competitor 2-7-0; long_low_dim (n=10): vs baseline 10-0-0, vs competitor 5-5-0; short_high_dim (n=9): vs baseline 9-0-0, vs competitor 3-6-0; short_low_dim (n=2): vs baseline 2-0-0, vs competitor 0-2-0.

`basal_token_bucket` by subregion: heavy_overload (n=16): vs baseline 16-0-0, vs competitor 13-3-0; overload (n=7): vs baseline 7-0-0, vs competitor 7-0-0; underload (n=7): vs baseline 0-7-0, vs competitor 0-7-0.

`binpack_cpsat` by subregion: large_items (n=9): vs baseline 6-1-2, vs competitor 1-1-7; mixed (n=13): vs baseline 5-0-8, vs competitor 0-0-13; triplet_like (n=8): vs baseline 8-0-0, vs competitor 0-0-8.

`blackbox_multistart_lbfgsb` by subregion: multimodal (n=20): vs baseline 17-0-3, vs competitor 3-15-2; unimodal (n=10): vs baseline 1-0-9, vs competitor 4-0-6.

`collective_auction` by subregion: ample_dense (n=8): vs baseline 8-0-0, vs competitor 0-0-8; ample_sparse (n=6): vs baseline 2-0-4, vs competitor 0-0-6; scarce_dense (n=15): vs baseline 15-0-0, vs competitor 0-0-15; scarce_sparse (n=1): vs baseline 1-0-0, vs competitor 0-0-1.

`community_louvain` by subregion: unweighted_dense (n=14): vs baseline 12-0-2, vs competitor 12-0-2; unweighted_sparse (n=9): vs baseline 8-0-1, vs competitor 9-0-0; weighted_dense (n=4): vs baseline 4-0-0, vs competitor 4-0-0; weighted_sparse (n=3): vs baseline 3-0-0, vs competitor 3-0-0.

`crowd_weighted_vote` by subregion: dense_binary (n=2): vs baseline 2-0-0, vs competitor 1-1-0; dense_multiclass (n=13): vs baseline 13-0-0, vs competitor 10-1-2; sparse_binary (n=3): vs baseline 3-0-0, vs competitor 3-0-0; sparse_multiclass (n=12): vs baseline 12-0-0, vs competitor 12-0-0.

`develop_diffusion` by subregion: few_seeds_dense (n=14): vs baseline 9-5-0, vs competitor 2-12-0; few_seeds_sparse (n=10): vs baseline 2-8-0, vs competitor 3-7-0; more_seeds_dense (n=5): vs baseline 3-2-0, vs competitor 3-1-1; more_seeds_sparse (n=1): vs baseline 1-0-0, vs competitor 1-0-0.

`graph_node_cut_exact` by subregion: beyond_flow_maxflow_bounds (n=7): vs baseline 4-0-3, vs competitor 7-0-0; within_flow_maxflow_bounds (n=23): vs baseline 3-0-20, vs competitor 0-0-23.

`maxsat_cpsat` by subregion: hard_and_soft (n=14): vs baseline 14-0-0, vs competitor 1-0-13; soft_only (n=8): vs baseline 7-0-1, vs competitor 0-0-8; unit_claims (n=8): vs baseline 4-0-4, vs competitor 3-0-5.

`reconcile_qp` by subregion: balanced_network (n=23): vs baseline 19-0-4, vs competitor 2-0-21; budget_split (n=7): vs baseline 7-0-0, vs competitor 0-0-7.

## Reading

**Prediction against outcome.** The pre-registration recorded development-only expectations.
- **Matched (six):** `binpack_cpsat`, `community_louvain`, `crowd_weighted_vote`, `graph_node_cut_exact`,
  `collective_auction` and `develop_diffusion`.
- **Differed (five):**
  - `maxsat_cpsat` came out DEFAULT, not NICHE: it was no slower than Z3 here and won 4-0.
  - `reconcile_qp` came out NICHE, not SUPERSEDED: it ties SLSQP on 28 of 30, wins 2 and is slower.
  - `blackbox_multistart_lbfgsb` came out DEFAULT, not EXPERIMENTAL; see the caveat below.
  - `basal_token_bucket` came out DEFAULT, not EXPERIMENTAL: it beats bid-price 20-10 (p = 0.049).
  - `basal_nlms` came out NICHE, not DEFAULT: RLS is significantly better (10-20, p_worse = 0.049).

**Where the rule's verdict and the evidence point different ways (reported, not re-decided):**
- **`blackbox_multistart_lbfgsb` is DEFAULT even though differential evolution wins 15-7 overall.**
  - On multimodal objectives DE wins 15-3.
  - The rule reads DE's advantage as not significant (p_worse = 0.067 against alpha 0.05), and the latency
    condition holds.
  - The proposed routing for multimodal continuous objectives is the competitor, DE.
- **`basal_token_bucket` loses every underload instance (0-7) to both arms.** Its win is the overload regime.
- **`graph_node_cut_exact`'s 7-0 against `flow_maxflow` comes entirely from the 7 instances beyond that genome's
  bounds.** Within the bounds it is 23 ties. This is bounds coverage, as pre-registered; the exact certificate adds
  nothing on the shared range.
- **`maxsat_cpsat` beats Z3 Optimize 4-0.** Three of those wins are on `unit_claims` instances, where development had
  already caught Z3 returning wrong optima.
- **`develop_diffusion` is REJECTED.** It made 3 wrong answers and loses 9-20 to Louvain plus seed vote. This is the
  known failure of harmonic propagation with few seeds.

**What this changes:**
- Seven new genomes are routable at 1.0.0 (DEFAULT) and two as niche capabilities. None is attached; attaching is the
  founder's decision (`docs/collaboration/FOUNDER-DECISIONS-2026-10-21.md`, D3).
- `collective_auction` (SUPERSEDED) and `develop_diffusion` (REJECTED) are excluded from routing.
- The evidence index is rebuilt from this file.
