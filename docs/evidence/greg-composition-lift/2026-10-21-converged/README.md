# P6 converged v1: recipe lifts re-measured on the converged Mind (2026-10-21)

**Converged VPL: 2 of 4 synthetic families** (F2R `identify_then_optimize`, F4 `bayes_then_voi`).
F1 has no lift because of one false answer. F3's composition ties the exact single genome.

## Why this run exists

The 2026-10-21 directive (section 6) says: "Bind verification to the actual integrated code. Do not transfer old
benchmark claims onto changed implementations." The converged compiler binds each recipe's complete code: its
closure, its stage genomes, the operation families its stages call and the organs serving its stage classes. Every
recipe verdict measured on a lineage freeze therefore routed UNEVALUATED. This run re-measures the four synthetic
families on the converged tree.

## Provenance

| item | value |
|---|---|
| runner | `cortex/evaluation/composition_lift/run_converged_v1.py` |
| pre-registration | `cortex/evaluation/composition_lift/prereg-converged-v1.json` (commit `d90cd6fb`) |
| freeze | `freeze-converged-v1.json`, commit `53d39d76`, sha256 `2d9b7f9f…0efd` (matches `manifest_sha256` in the results) |
| run | once, clean detached worktree at `53d39d76`, `python -I`, 16:16-16:29 UTC |
| results | `results-converged-v1.json`, `run.log` (one line per item) |
| seeds | F1 6501-6540, F2R 6601-6664, F3 6701-6740, F4 6801-6840: fresh, disjoint from `spent_seeds()` and #158's reservations |

A development check on dev seeds 1-2 ran before the freeze, and no held-out seed was generated before it. That
check found a compiler defect: the Fermi organ answered F1 requests and abstained. The defect was fixed before the
freeze (`compiler._reject_recipe_relaxations`); the pre-registration discloses it.

## Rule (frozen)

A family lifts when routed composition decides more items correctly than the best single arm, and adds no wrong
answer over it. The best single arm is the best of the lineage constituents and the admitted exact single genome,
chosen on held-out results. The lift also needs the one-sided exact sign test over discordant items to give
p < 0.05, and routed median latency within 60 s. The lineage rule (constituents only) is reported beside it.

## Results (held-out)

| family | n | routed correct / wrong / no decision | best single (correct / wrong) | W-L | p | converged | lineage rule |
|---|---|---|---|---|---|---|---|
| F1 estimate_then_optimize | 40 | 39 / 1 / 0 | optimize_at_worst_case (4 / 0) | 35-0 | 2.9e-11 | **no lift**: one wrong answer the best single does not make | no lift (same comparator) |
| F2R identify_then_optimize | 64 | 62 / 1 / 1 | optimize_on_association (48 / 16) | 16-2 | 0.00066 | **lift** | lift |
| F3 graph_then_allocate | 40 | 40 / 0 / 0 | exact_single `flow_expansion_mcf` (40 / 0) | 0-0 | 1.0 | **no lift**: tied | lift over greedy, 13-0 |
| F4 bayes_then_voi | 40 | 40 / 0 / 0 | voi_uninformed (25 / 15) | 15-0 | 3.1e-05 | **lift** | lift |

Reported outside the rule:

- **Latency (routed vs best single, median):**
  - F1: 0.95 s vs 0.58 s.
  - F2R: 1.10 s vs 0.58 s.
  - F3: 1.35 s vs 0.27 s. The composition costs about five times the exact single for the same answers.
  - F4: 0.83 s vs 0.56 s.
  - p95 latencies are in the results file.
- **Failures:**
  - Translation failures: 0 in every family.
  - Composition failures (routed state not ANSWERED): F2R 1 of 64 (F2R-6606, a no-decision); 0 elsewhere.
- **False answers:**
  - F1-6509: wrong on static, routed and compiled.
  - F2R-6640: wrong on all three.
  - The single comparators' false answers are larger. On F1, `optimize_at_point` was wrong on 36 of 40 items.
    The rule compares against `optimize_at_worst_case`: it ties `optimize_at_point` on correct answers and makes
    fewer wrong ones, which is the declared tie-break and the conservative comparator.
- **Compiled arm (the Competency Compiler, the canonical Layer 5 entry):**
  - It matched routed composition on F1, F2R and F4.
  - On F3 it chose `flow_expansion_mcf` at 0.28 s median, the simpler winner, and answered all 40 correctly.
- **Compiler version:** the compiled arm measured the compiler at `53d39d76`. `compiler.py` changed afterwards (the
  settled-outcome preference and the formed-mechanism receipt basis). Neither acts without settled outcomes or a
  formed mechanism, and neither is in any recipe's code binding: the recipe bindings at the new head equal the
  frozen ones.

## What changed in routing

The evidence index now takes these four verdicts as deciding: it is the latest measurement of these recipes, on
fresh instances, at the recipes' current code.

| recipe | verdict |
|---|---|
| `identify_then_optimize` | VPL_LIFT |
| `bayes_then_voi` | VPL_LIFT |
| `estimate_then_optimize` | NO_LIFT. It still serves F1 as the only fit (`only_fit_despite_no_lift`); the constituents are not invocable methods. |
| `graph_then_allocate` | NO_LIFT. `flow_expansion_mcf` is preferred where attached, as the twin-genome rule already did. |

Earlier verdicts stay in the index history. The natural-family recipes (`forecast_then_allocate`,
`forecast_then_staff`, `track_then_staff`) stay UNEVALUATED. Their held-out data were already looked at, so a re-run
would be diagnostic only and could not support a generalization claim.

## What this does not show

- Synthetic families only: no claim about natural data or realized outcomes.
- F1's lift claim is withdrawn on this code. That is not because composition is weak (35-0); it is because it made
  one false answer the conservative single did not, and the frozen rule counts that.
- No attachment, adoption or authority change.
