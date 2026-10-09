# P8 protected evolutionary cognition: first cycle, 2026-10-08

Engine `greg/cognition/evolution.py` (committed `fe222f4` before the cycle ran); sandbox
`greg/cognition/evolution_sandbox.py`; record `cycle-forecast-1.json` (full lineage of every candidate).
Run from a clean worktree at `fe222f4`, CPU cores 0-2, Landlock ABI 7 confinement confirmed in the record.

| Step | Result |
|---|---|
| Target | forecasting genome parameters (`forecast_quantile`): fit window, rolling origins, trend/damping grids, error model, interval scale |
| Pool | 201 M4 Weekly series outside Micro/Industry (P6 F5) and outside the 40 admission instances; 100 train / 101 held out |
| Recurring failure | incumbent worse than the naive Gaussian baseline on **45%** of train series (trigger 25%) |
| Search | 5 generations x 8, mutation + crossover inside the closed space; every candidate confined, inputs only |
| Best candidate | `cfg-7a845995e588` (fit window 156, origins 156, interval scale 0.943): train loss 0.7383 vs 0.7791 (-5.2%) |
| Adversarial | all outputs independently verified; short histories 0.949 vs 0.935 (+1.5%, within 5%); level shift 1.447 vs 1.657 |
| Held out (one look) | candidate **worse**: 42 wins / 59 losses, p = 0.96; mean loss 0.7779 vs 0.7537 (+3.2%) |
| Decision | **REJECT**. No proposal; nothing changed. |

## Reading

The protection worked as designed. The search found a configuration that was 5.2% better on train and passed the adversarial checks, but it was 3.2% worse on series it had never seen. The protocol rejected it, so no overfit change reached GREG's cognition.

The cycle did not improve the forecaster. This is negative evidence about this configuration space, not about the mechanism. It also confirms the founder's warning that evaluator access, not search, is the safety boundary.

This held-out split is now spent for this target. A later cycle on the forecaster needs a fresh split, such as a new M4 frequency or later data, so it cannot select on this one.

## Protections exercised (tests: `tests/unit/test_greg_protected_evolution.py`)

- Candidates are data in a closed space. Any key naming constitutional or evaluation state is refused: authority, budget, shutdown, target, evaluator, threshold, acceptance, seal, label, truth, score, held-out.
- Candidates run network-denied and Landlock-confined, and receive inputs only. Reading the evaluator's data file from inside the sandbox is denied (`PermissionError`).
- The `SealedEvaluator` digest covers evaluator code, outcomes, inputs and rule. An edited outcome raises `EVALUATOR_TAMPERED`.
- RETAIN produces only a `PROPOSED_NOT_APPLIED` proposal with a rollback and a canary. Adoption is a reviewed change.
