# P8 cycle 3: the constraint-release search policy, 2026-10-14

- **Target:** the search policy of `develop_constraint_release` (version 1.2.0). This is a closed data space (`CR_CONFIG_SPACE`): population, offspring, recombination and extra-mutation probabilities, tournament size, and a random-restart share. A candidate is data, never code.
- **Why this target:** admission v2 measured headroom. Random restart, with the same budget and retain rule, beat the incumbent search 15-5 on fresh seeds.
- **Pre-registration:** commit `5287303` fixed the target, the seeds (train 7200-7259, held-out 7300-7389), the stress sets (an evaluation budget of 16; validation cut to four cases) and the unchanged P8 rule before any of those instances was generated.
- **Run:** once, in a clean worktree at that commit, pinned to one core. The candidates ran Landlock-confined (ABI 7). `cycle-cr-3.json` is the unedited record and `cycle-cr-3.log` is its console output.

## Result: REJECT at the adversarial gate (held-out set unspent)

| Step | Measured |
|---|---|
| Trigger: incumbent worse than random restart on train items | 15 of 60 (rate 0.25, trigger 0.25): the cycle proceeds |
| Residual geometry | failing items: tight due dates 9 of 28, loose 6 of 32; bimodal processing times 9 of 30, uniform 6 of 30 |
| Search | 38 configurations over 5 generations |
| Best candidate (`cfg-86c2f27f6580`) | recombination probability 0.3 -> 0.13, extra mutation 0.3 -> 0.259; train mean loss 0.006599 -> 0.005283 (20% lower) |
| Stress: lean budget (16) | incumbent 0.00769, candidate 0.00641: better |
| Stress: validation cut to four cases | incumbent 0.010402, candidate 0.011054: **6.3% worse**, beyond the frozen 5% tolerance |
| All candidate outputs verified independently | yes |
| Decision | **REJECT** ("adversarial evaluation failed"); held-out comparison not run |

## What this shows

- **P8 protects the evaluator, again.** Section 31 item 7 (protected evolution improves cognition) remains **not met**, after three cycles and three rejections. Each rejection came from a different gate: held-out (cycle 1), scarce-sample stress (cycle 2), and stress on scarce validation (cycle 3).
- **The candidate's gain on training did not survive a validation split cut to four cases.** Less recombination pays when the validation set can tell configurations apart. With four validation cases the retain-or-extinct step selects on noise, and the policy that explored more conservatively did worse there. The incumbent's 0.3 recombination is more robust to a small validation set.
- **The random-restart share did not help on training.** The best configuration that used it (`cfg-633e98645331`, third by train loss) also lowered recombination. The headroom random restart showed in admission is not captured by blending it into the evolutionary search at these budgets.
- **The held-out set (7300-7389) is unspent.** A later, separately pre-registered cycle may use it. That cycle must not re-run this one with a relaxed stress tolerance: the tolerance is part of the frozen rule.

## Not changed by this record

No configuration was proposed or applied. `CR_DEFAULT_CONFIG` stays the admitted search. The evidence index is unaffected; the genome's status is stale at 1.2.0 until re-admitted.
