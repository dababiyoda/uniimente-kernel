# Genome admission v10: the meta wave (2026-11-05)

Three directive-named families that had no executor, built in parallel lanes and admitted once under the unchanged
rule.

| Step | Commit |
|---|---|
| Pre-registered | `e48292d3` |
| Frozen | `0493e706` |
| Run once | clean detached worktree, one pinned core, 04:50:59 to 04:51:06Z |

- **Run:** source commit `0493e706`, source dirty [], freeze `sha256:0cf370a98ee4be03…`, finished 2026-11-05T04:51:06.282848+00:00.
- **Host load:** start {'1m': 0.64, '5m': 0.87, '15m': 0.97, 'runnable': 1, 'entities': 105}, end {'1m': 0.67, '5m': 0.87, '15m': 0.97, 'runnable': 1, 'entities': 102} (diagnostic only).

| Family | Layer | Version | Status | Candidate correct/wrong/abstain | vs baseline W-L-T (p better) | vs competitor W-L-T (p better / p worse) | Median s (candidate / baseline / competitor) | Canonical path |
|---|---|---|---|---|---|---|---|---|
| `collective_ecology_bidding` | 2 | 1.0.0 | **DEFAULT_FOR_GEOMETRY** | 30/0/0 | 23-7-0 (0.002611) | 13-17-0 (0.819203 / 0.292332) | 0.003448 / 0.000128 / 0.003194 | STRUCTURALLY_VERIFIED |
| `meta_active_inference` | 5 | 1.0.0 | **SUPERSEDED** | 30/0/0 | 28-2-0 (0.0) | 0-24-6 (1.0 / 0.0) | 0.0029 / 0.00033 / 0.001352 | STRUCTURALLY_VERIFIED |
| `meta_global_workspace` | 5 | 1.0.0 | **NICHE_CAPABILITY** | 30/0/0 | 25-3-2 (1.4e-05) | 9-10-11 (0.676197 / 0.5) | 0.00094 / 0.000326 / 0.000615 | STRUCTURALLY_VERIFIED |

`collective_ecology_bidding` by subregion: deep_history/loose_budget (n=6): vs baseline 6-0-0, vs competitor 2-4-0; deep_history/tight_budget (n=6): vs baseline 5-1-0, vs competitor 2-4-0; sparse_history/loose_budget (n=9): vs baseline 4-5-0, vs competitor 3-6-0; sparse_history/tight_budget (n=9): vs baseline 8-1-0, vs competitor 6-3-0.

`meta_active_inference` by subregion: binary_tests (n=10): vs baseline 9-1-0, vs competitor 0-7-3; mixed_tests (n=10): vs baseline 9-1-0, vs competitor 0-10-0; ternary_tests (n=10): vs baseline 10-0-0, vs competitor 0-7-3.

`meta_global_workspace` by subregion: narrow_bus_strong_cross (n=7): vs baseline 7-0-0, vs competitor 4-1-2; narrow_bus_weak_cross (n=1): vs baseline 1-0-0, vs competitor 0-1-0; wide_bus_strong_cross (n=15): vs baseline 11-3-1, vs competitor 4-7-4; wide_bus_weak_cross (n=7): vs baseline 6-0-1, vs competitor 1-1-5.

## Reading

**Ecology bidding: DEFAULT, and the reason must be read precisely.**
- **Against the static baseline:** 23-7 (p = 0.003).
- **Against the competitor:** it loses 13-17 to the certainty-equivalent allocator, not significant. That competitor is the same planner fed posterior means, without reputation-kept optimism.
- **Why DEFAULT:** the rule's verdict rests on the baseline win, a competitor loss that is not significant, and latency within 1.25x (1.08x).
- **What it does not show:** that the bidding market adds value over certainty equivalence. On this evidence the reputation mechanism is neutral to slightly harmful. As the lane predicted, reputations collapse within a few runs and the candidate converges on its competitor.
- **What it does show:** an executable ecology allocator, verified on GREG's canonical path, that clearly beats static allocation of a compute budget. Learned allocation of compute among solver species is now routable.

**Global workspace: NICHE.**
- It beats independent specialists 25-3-2 (p = 0.00001).
- It ties the sequential token ring 9-10-11.
- It is 1.53x slower than the token ring, beyond the 1.25x latency allowance. The extra latency is the cost of salience arbitration, so it is NICHE, not DEFAULT.
- **The edge:** it is on narrow buses with strong cross-block coupling (4-1 against the token ring). Its weakness is wide buses with strong coupling (4-7), where synchronous broadcast oscillates, as the lane recorded on development seeds.
- **Scope:** it arbitrates among one problem's block specialists. Arbitration among GREG's intelligences on a mixed suite stays open in the reserved record.

**Active inference: SUPERSEDED, decisively.**
- It beats the cheapest-first baseline 28-2, but loses 0-24-6 to horizon-2 Bayesian decision theory without the epistemic term.
- The information-gain bonus values information the risk term already prices, so the agent buys tests that do not pay. This replicates the development finding (0-8-2).
- On this geometry, the strongest objective is expected loss alone. Active inference is excluded from routing, and the result is kept as evidence that the epistemic term, as specified, harms fault diagnosis.

**What changes:**
- 86 executable genomes now carry current-version evidence: 46 DEFAULT, 18 NICHE, 13 SUPERSEDED, 3 COMPOSITION_ONLY, 4 EXPERIMENTAL, 2 REJECTED, so 64 are admitted.
- None is attached; attaching is the founder's decision.
- The reserved record names the executors. The global workspace is recorded as a partial precursor.

**Limits:**
- Every instance is synthetic. Fault diagnosis and spin glasses are mathematical; the ecology world is declared and simulated.
- The ecology and active-inference competitors are ablations of their candidates. Each verdict isolates one mechanism; it is not a test against a structurally different method.
- The exposure-ledger rebuild for the freeze commit ran in another process while this run was in progress. The host load stayed at 0.6-0.7 and the load figures are diagnostic only.
- Authority: none created. VEPMC: 0.
