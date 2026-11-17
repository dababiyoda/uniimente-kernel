# Genome admission v6 (2026-10-21): both repair families NICHE_CAPABILITY

- **Pre-registration:** [`PREREGISTRATION.md`](PREREGISTRATION.md), committed in `b33fd678` and promoted unchanged from the lane draft `../2026-10-21-v6-draft-repair.md`.
- **Freeze:** [`freeze.json`](freeze.json), committed in `f33cb2a9` before any held-out instance was generated. The exposure ledger that cites this freeze follows in `99048eda`: the ledger records the freeze's own commit, so it cannot be in that commit. The freeze commit's message says otherwise; this sentence corrects it.
- **Run:** once, from a clean detached worktree of `f33cb2a9`, under `taskset -c 1`, load about 0.9, 9 s wall. Outputs: [`results.json`](results.json) and [`run.log`](run.log).
- **Rule:** `RULE` verbatim, unchanged. Held-out seeds 1500-1529, through `repair_instance`. Both families are scored on identical held-out instances.

## Generated from results.json (`scripts/admission_readme.py`)

- **Run:** source commit `f33cb2a9`, source dirty [], freeze `sha256:c7c6dfa7c3d6a10d…`, finished 2026-10-21T20:22:07.614734+00:00.
- **Host load:** start {'1m': 0.91, '5m': 0.93, '15m': 0.97, 'runnable': 1, 'entities': 108}, end {'1m': 0.92, '5m': 0.93, '15m': 0.97, 'runnable': 1, 'entities': 105} (diagnostic only).

| Family | Layer | Version | Status | Candidate correct/wrong/abstain | vs baseline W-L-T (p better) | vs competitor W-L-T (p better / p worse) | Median s (candidate / baseline / competitor) | Canonical path |
|---|---|---|---|---|---|---|---|---|
| `develop_repair` | 4 | 1.1.2 | **NICHE_CAPABILITY** | 30/0/0 | 30-0-0 (0.0) | 7-23-0 (0.999285 / 0.002611) | 0.027451 / 0.000327 / 0.000826 | STRUCTURALLY_VERIFIED |
| `develop_repair_hybrid` | 4 | 1.0.0 | **NICHE_CAPABILITY** | 30/0/0 | 23-7-0 (0.002611) | 7-7-16 (0.604736 / 0.604736) | 0.084921 / 0.027727 / 0.000919 | STRUCTURALLY_VERIFIED |

`develop_repair` by subregion: reliable_controller (n=15): vs baseline 15-0-0, vs competitor 0-15-0; unreliable_controller (n=15): vs baseline 15-0-0, vs competitor 7-8-0.

`develop_repair_hybrid` by subregion: crashed_controller (n=5): vs baseline 5-0-0, vs competitor 4-0-1; reliable_controller (n=15): vs baseline 15-0-0, vs competitor 0-0-15; stale_controller (n=10): vs baseline 3-7-0, vs competitor 3-7-0.

## Reading

- **`develop_repair` 1.1.2 replicates.** NICHE_CAPABILITY at the version P8 bumped. It beats no repair 30-0 and loses to the central replanner 7-23, the same record as admission v2 at 1.1.1. Its 7 wins all come where the controller is unreliable. Where the controller is reliable the replanner wins 15-0. Step A of the P8 repair target (its constants became data) changed no verdict.
- **`develop_repair_hybrid` 1.0.0 is NICHE_CAPABILITY, not DEFAULT.**
  - **Against the local rules (its baseline):** 23-7 (p = 0.0026).
  - **Against the replanner (its competitor):** 7-7 with 16 ties, so neither side is significantly better.
  - **Wrong answers:** the hybrid has 0 wrong answers against the replanner's 3. Mean quality is 0.981 against 0.680.
  - **Why not DEFAULT:** the rule requires the candidate to be significantly better than the competitor or within 1.25x of its median latency. The hybrid is neither: its median is 0.085 s against 0.0009 s, about 92x. It replays the planner once per step.
- **The exploratory run's predicted weakness replicates on fresh data.**
  - **Stale controllers (n = 10):** the hybrid loses 3-7 to the replanner and 3-7 to the local rules. The exploratory run (seeds 4000-4639) found 37-126 here, and its declaration predicted it: the audit fires at step 0, the standby is woken, and its message bill is already paid when the planner catches up.
  - **Crashed controllers:** the hybrid wins 4-0-1.
  - **Reliable controllers:** the two tie 15 of 15, with identical outputs.
  - **The net:** the hybrid trades losses on stale items for wins on crashed ones, and it removes every false claim.
- **What a NICHE verdict changes:** both genomes are routable at these versions. Neither is attached; attaching either is the founder's decision.
- **What it does not show:** every instance is simulated, including the controller failure modes and the message-loss model. Thirty items give 5 crashed and 10 stale controllers, so the subregion counts are small and descriptive only. Zero wrong answers in 30 items does not prove zero risk: the one-sided 95% upper bound is about 9.5%.
- **The cheapest next improvement** is the one the exploratory README named: a standby that can return to sleep once the planner's field audits clean again. That needs a resumable local protocol, which is not built. If built, it would be a new version and need a fresh admission.
