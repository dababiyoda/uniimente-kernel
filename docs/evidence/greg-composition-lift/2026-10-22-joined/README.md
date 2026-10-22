# P6 joined v1: recipe lifts re-measured on the joined integration tree (2026-10-22)

**Joined VPL: 3 of 4 synthetic families** (F1 `estimate_then_optimize`, F2R `identify_then_optimize`, F4
`bayes_then_voi`). F3 `graph_then_allocate` is NO_LIFT: the exact single genome `flow_expansion_mcf` ties it on
every item at about a fifth of the latency.

## Why this run exists

On the joined tree (`claude/greg-full-machine-completion-whgiee` at `ea90b4b4`: #192, the portfolio chain, Cortex
0.2.2, Track B #189 with its review fixes, #179 and #158) every recipe verdict was stale.
`greg.cognition.compiler.recipe_stale` named a changed recipe closure for all seven recipes, because the joined
`cortex.reason` (grant-window guard) and the composition and stage solvers changed under the code that P6 converged
v1 measured at `53d39d76`. Live VPL on the joined tree was therefore 0. The founder's rule is to bind verification to
the actual integrated code and not to transfer old claims. This run re-measures the four synthetic families on the
joined code, on fresh held-out seeds.

## Provenance

| item | value |
|---|---|
| runner | `cortex/evaluation/composition_lift/run_joined_v1.py`: a private instance of `run_converged_v1.py`, executed unchanged; only identity, paths and seeds are overridden |
| pre-registration | `cortex/evaluation/composition_lift/prereg-joined-v1.json`, commit `aaaa1c26` |
| freeze | `freeze-joined-v1.json`, commit `8d81f342`, sha256 `3fd5d987…9d28` (equals `manifest_sha256` in the results); binds 27 file digests and the four recipes' complete code bindings |
| run | once, clean detached worktree `/home/user/wt-p6-run` at `8d81f342`, `taskset -c 3 python -I`, 04:49:55-05:01:12 UTC |
| environment | CPython 3.11.17, Intel Xeon @ 2.10GHz, 4 CPUs, affinity `[3]`, `isolated: true` (recorded in the results) |
| results | `results-joined-v1.json` (with its own `limits` block; `limits-joined-v1.json` is a copy of it), `run.log` (one line per item, then the summary; the final `EXIT 0` line was appended by the launching shell), `contention-sampler.log` |
| seeds | F1 4717-4756, F2R 4640-4703, F3 4809-4848, F4 4863-4902 |

**Seed check.** A script compared these seeds with `spent_seeds()`, the development seeds (0-199), P8_RESERVED,
3000-3999, every seed-named integer or range in the 94 tracked `*freeze*`, `*prereg*` and `*suite*` JSON files, and the
seed ranges of all 443 exposure-ledger records. Its result:

- there is no overlap with spent seeds, development seeds, reservations or any freeze or pre-registration;
- **disclosed numeric overlaps, none with a P6 generator:**
  - The #158 immune-8 review pilot covers 4000-4999 in the ledger (`collective:immune_gaussian_instance`). Every seed
    in this lane's assigned range therefore shares a number with it. The ranges were taken from 4640-4999 to avoid the
    `develop_repair_hybrid` pilot (4000-4639) as well.
  - Seed 4895 appears as a payload seed in `crossgeo-heldout-v0.2.json`, a cortex crossgeo item with its own
    generator.

**Development check** (dev seeds 1-2, before the freeze, disclosed in the pre-registration): every arm executed, and
all 8 items were answered correctly by static, routed and compiled. No defect was found and no code changed.

## Rule (frozen; v1's rule unchanged)

A family lifts when four conditions hold:

- routed composition decides more held-out items correctly than the best single arm;
- it adds no wrong answer over that arm;
- the one-sided exact sign test over discordant items gives p < 0.05;
- routed median latency is within 60 s.

The best single arm is the best of the lineage constituents and the admitted exact single genome, chosen on held-out
results.

## Results (held-out)

| family | n | routed correct / wrong / suboptimal / no decision | best single (correct / wrong) | W-L | p (one-sided) | median latency routed vs best single | verdict | lineage rule |
|---|---|---|---|---|---|---|---|---|
| F1 estimate_then_optimize | 40 | 39 / 0 / 1 / 0 | optimize_at_worst_case (4 / 0; 36 suboptimal) | 35-0 | 2.9e-11 | 0.853 s vs 0.502 s | **LIFT** | lift |
| F2R identify_then_optimize | 64 | 60 / 4 / 0 / 0 | optimize_on_association (49 / 15) | 13-2 | 0.0037 | 0.940 s vs 0.512 s | **LIFT** | lift |
| F3 graph_then_allocate | 40 | 40 / 0 / 0 / 0 | exact_single `flow_expansion_mcf` (40 / 0) | 0-0 | 1.0 | 1.206 s vs 0.234 s | **NO_LIFT**: tied | lift over greedy, 14-0, p 6.1e-05 |
| F4 bayes_then_voi | 40 | 40 / 0 / 0 / 0 | voi_uninformed (20 / 20) | 20-0 | 9.5e-07 | 0.730 s vs 0.498 s | **LIFT** | lift |

Reported outside the rule:

- **False answers:**
  - F2R: routed composition made 4 wrong answers (F2R-4657, -4662, -4682, -4702). The static and compiled arms made
    the same 4. The best single made 15, and was correct on two of the four (4657, 4662); these are the 2 losses.
  - F1: no wrong answer. F1-4753 is suboptimal on static, routed and compiled.
  - The single comparators were wrong more often:
    - F1 `optimize_at_point`: 38 of 40.
    - F4 `bayes_alone`: 22 of 40; `voi_uninformed`: 20 of 40.
- **Abstentions (no decision):**
  - 0 on routed, static and compiled in every family.
  - The constituents `estimate_alone` (F1) and `identify_alone` (F2R) abstained on every item by construction.
- **Failures:** translation failures 0 and composition failures (routed state not ANSWERED) 0 in every family.
- **Latency:**
  - Routed composition costs 1.70x (F1), 1.84x (F2R) and 1.47x (F4) the best single's median latency, and 5.15x on F3.
  - p95 routed: F1 0.927 s, F2R 1.019 s, F3 1.320 s, F4 0.811 s.
- **Compiled arm** (Competency Compiler, canonical Layer 5 entry):
  - It matched routed composition item for item on F1, F2R and F4.
  - On F3 it answered all 40 correctly at 0.255 s median, routing to the simpler exact genome.
- **CPU contention:** at launch the load average was 0.37 and no other CPU-bound process ran. From about 04:51 UTC
  another session's test suite ran on cores 0-2: `greg.appraisal`, cortex workers from `/home/user/uniimente-kernel`
  and `/home/user/wt-168-base`, and pytest `greg` bodies. The load average rose to 3.51 by 05:00:53 (sampled every
  30 s in `contention-sampler.log`). The run was pinned to core 3 throughout, but caches and memory bandwidth were
  shared. Latencies are this machine's under that contention. Only the 60 s median budget is in the rule, and every
  family is far inside it.

## Against converged v1 (53d39d76, seeds 6501-6840)

| family | converged v1 | joined v1 |
|---|---|---|
| F1 | NO_LIFT: 35-0 but 1 wrong answer (F1-6509) | LIFT: 35-0, 0 wrong, 1 suboptimal |
| F2R | LIFT 16-2, 1 wrong, 1 no decision | LIFT 13-2, 4 wrong, 0 no decision |
| F3 | NO_LIFT, tied by `flow_expansion_mcf` | NO_LIFT, tied by `flow_expansion_mcf` |
| F4 | LIFT 15-0 | LIFT 20-0 |

These are different held-out instances on different code, so the comparison is not a paired test.

- **F1:** the flip from NO_LIFT to LIFT rests on 0 wrong answers in this sample, against 1 in v1's. The rule is
  binary on one item. This is a sample near the rule's boundary, not evidence that the joined code fixed a false
  answer.
- **F2R:** 4 wrong answers here against 1 in v1. That is reported, not explained.

## What changed in routing

`scripts/build_mind_evidence_index.py` lists this results file after converged v1, so for these four recipes its
verdicts decide. They bind the recipe code at `8d81f342`, which equals the joined tree's recipe code.

- `estimate_then_optimize`, `identify_then_optimize` and `bayes_then_voi` route as VPL_LIFT.
- `graph_then_allocate` is NO_LIFT, with `flow_expansion_mcf` preferred.
- The natural-family recipes (`forecast_then_allocate`, `forecast_then_staff`, `track_then_staff`) stay stale on the
  joined code. Their held-out data were already looked at, so re-running them would be diagnostic only.

## What this does not show

- Synthetic families only: no claim about natural data or realized outcomes.
- No attachment, adoption, merge or authority change.
