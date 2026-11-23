# Operation-family admission v3: #155's families re-admitted on the converged tree (2026-10-16)

- **What this is:** the first run of a live harness for PR #155's operation families, closing review of #179 M17.
  #155's own runners refuse on this tree by design (`FROZEN_INPUT_CHANGED`).
- **Pre-registration:** `cortex/evaluation/genome_admission/prereg-ops-v3.json`, committed with the runner at
  `1213394`.
- **Freeze:** `freeze-ops-v3.json`, committed at `dfdcfe9`. It binds the digests of the runner and the three
  reused runners, plus the static dependency closure of every benchmarked family's dispatched solver.
- **Run:** once, in a fresh detached worktree at `dfdcfe9`, under `python -I`. Load average was 0.28 at the start.
  The run took 30 s and exited 0. No other run on seeds 5001-5040 happened.
- **Benchmarks, arms and rule:** v1, v2 and the sparse-crowd test, imported unchanged. v1's frozen status rule.
- **Development check, disclosed in the pre-registration:** seeds 1-3 only, to check that the benchmarks execute.

## Result (copied from `results-ops-v3.json`)

| family | v3 status | vs baseline | vs competitor | #155 lineage | reading |
|---|---|---:|---:|---|---|
| probabilistic | DEFAULT_FOR_GEOMETRY | 26-10 | 24-12 | DEFAULT | replicates |
| control | DEFAULT_FOR_GEOMETRY | 39-1 | 40-0 | DEFAULT | replicates |
| micro | DEFAULT_FOR_GEOMETRY | 36-4 | none | DEFAULT | replicates |
| sequential | DEFAULT_FOR_GEOMETRY | 13-0 | none | DEFAULT | replicates |
| information | DEFAULT_FOR_GEOMETRY | 24-0 | 16-0 | DEFAULT | replicates |
| game | DEFAULT_FOR_GEOMETRY | 40-0 | 31-0 | DEFAULT | replicates |
| exact | DEFAULT_FOR_GEOMETRY | 40-0 | none | DEFAULT | replicates |
| crowd (v2 geometry) | DEFAULT_FOR_GEOMETRY | 26-10 | 14-21 | DEFAULT | replicates |
| swarm | DEFAULT_FOR_GEOMETRY | 37-3 | 17-21 | DEFAULT | replicates |
| blackbox | SUPERSEDED | 38-2 | 11-23 | SUPERSEDED | replicates (multistart L-BFGS-B wins) |
| pattern | REJECTED | 7-22 | 0-23 | REJECTED | replicates |
| evolutionary | REJECTED | 0-40 | none | REJECTED | replicates |
| simulation | REJECTED | 0-40 | none | REJECTED | replicates |
| crowd (sparse geometry) | EXPERIMENTAL | 24-15 | 12-27 | EXPERIMENTAL | replicates |
| graph | **EXPERIMENTAL** | 4-0 (p = 0.0625) | none | DEFAULT | **disagrees** |
| robust_pattern | **DEFAULT_FOR_GEOMETRY** | 14-5 (p = 0.032) | 4-7 | EXPERIMENTAL | **disagrees** |
| collective | **EXPERIMENTAL** | 14-8 | 5-10 | REJECTED (erratum: EXPERIMENTAL) | **disagrees** with the raw label, agrees with the erratum |

Statuses replicate for 14 of 17 rows (16 families plus the sparse-crowd geometry). The disagreements are reported
as the pre-registration requires: both runs stay in history, and nothing is resolved post hoc.

- **graph:** Dijkstra and fewest-hops BFS return paths of equal weight on 36 of 40 items, so only 4 discordant
  items remain. 4-0 cannot reach p < 0.05. The candidate never loses. On this geometry the rule cannot separate
  them at n = 40, and the route rests on the latest reading, EXPERIMENTAL.
- **robust_pattern:** median/MAD now beats Tukey fences at p = 0.032. Rosner's generalized ESD, the competitor,
  ties it at 4-7. #155's reading was EXPERIMENTAL. Both readings sit near the rule boundary.
- **collective:** the run reads EXPERIMENTAL against a baseline that knows hidden accuracies (review of #179,
  M3). That matches the index's erratum. A pre-registered comparison against deployable baselines is still owed.
- **Observation outside the rule:** on the sparse geometry, the one-step agreement-weighted vote beats
  Dawid-Skene 27-12 (p = 0.012). The status stays EXPERIMENTAL because the rule names SUPERSEDED only when the
  candidate first beats the baseline. This replicates #155's sparse finding: the simpler vote is the stronger
  method there.

## Binding and consumption

- **Index:** `scripts/build_mind_evidence_index.py` appends this file to `OPERATION_RUNS` after #155's three runs,
  so its rows set the routed status and every earlier verdict stays in `history`.
- **Code binding:** each positive verdict binds the closure of the solver its run dispatched at `dfdcfe9`
  (`greg.cognition.code_binding`). A later change to any closure member routes the family as UNEVALUATED
  until this harness runs again under a new freeze path.
- **Limits:** these are synthetic native geometries, not real-world outcomes. Latency is a diagnostic only. No
  family is attached by this run.
