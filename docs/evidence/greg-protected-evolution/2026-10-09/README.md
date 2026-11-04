# P8 protected evolutionary cognition: second cycle (negative-selection detector), 2026-10-09

- **Engine:** `greg/cognition/evolution.py`, target `immune_detect`, committed in `ed4ee29` before the cycle ran.
- **Record:** `cycle-immune-2.json` (full lineage of all 34 evaluated configurations); console output in `cycle-immune-2.log`.
- **Run:** a clean worktree at `ed4ee29`, on CPU cores 0-2, with Landlock confinement recorded.

| Step | Result |
|---|---|
| Target | `collective_immune` configuration: detector count, uniform share, scale set, calibration folds, alarm fraction, diagonal or full whitening. Closed space; the default configuration is byte-identical to the reviewed genome on all 10 dev seeds. |
| Split | Fresh seeded instances: train 7000-7039 (40), held out 8000-8059 (60). Disjoint from admission seeds 0-9 and 1000-1029. |
| Recurring failure | The incumbent is worse than the per-feature z-score baseline on **40%** of train items (trigger 25%). It is worst at the tightest false-alarm budget: 7 of 12 items at 0.01. |
| Search | 5 generations × 8; every candidate ran confined and received inputs only. |
| Best candidate | `cfg-7e4fdadb262f`: full whitening, alarm fraction 0.866, a single detector scale, 3000 detectors. Train mean loss −0.493. The incumbent's train mean is +∞ because it gives a false-alarm violation on s7002. |
| Adversarial | **Failed.** On `scarce:s7002` (80 self samples) the candidate violates the false-alarm tolerance and the incumbent does not. The candidate's scarce-set mean loss is +∞ against −0.271 for the incumbent. Both violate on `strict:s7002`. |
| Held out | **Not evaluated.** The cycle stops before the held-out look, so seeds 8000-8059 remain unspent. |
| Decision | **REJECT**. No proposal; nothing changed. |

## Reading

- **The stress gate caught a real fragility the train metric could not see.**
  - Full whitening estimates a full covariance from the self samples.
  - A higher alarm fraction spends more of the false-alarm budget.
  - On 40-500 samples this helped (train −0.493).
  - On 80 samples it produced a false-alarm violation, the one failure a detector must not trade for F1.
  - The rule rejected the candidate before it could be adopted.
- **The shipped detector has its own weakness, now on record.**
  - It gave a false-alarm violation on train item s7002.
  - The cross-fitted conformal calibration bounds the expected false-alarm rate. It does not bound every instance below the score's binomial 95% limit.
  - This weakness is evidence for the held-out admission, not something P8 fixed.

## Harness defects found while recording this cycle (fixed in `94d2295`; the decision is unchanged)

1. **Infinite incumbent loss.** `relative_gain` divided by an infinite incumbent mean (a wrong answer) and returned NaN. NaN slipped through the `> 1%` gate because the comparison was False. The candidate genuinely had fewer wrong answers on train, so the fixed rule (gain +∞) advances it the same way.
2. **Abstentions counted as failed verification.** Abstentions (output `None`) were passed to the verifier and counted as refutations, so `all_outputs_verified` read false. Rerunning the candidate on every stress item in-process found **0** refuted answers. The stress-set worsening alone makes the decision REJECT.

A rerun with the same search seed would select the same candidate and fail the same stress item. It was therefore not repeated.

## Protections exercised

- **Closed configuration space.** Protected names are refused, including `alarm_threshold`.
- **Evaluator isolation.** The sealed evaluator holds the labels in the parent process only. Candidates receive inputs only and are denied reads of repository files.
- **Allow-listed method.** The sandbox imports only the reviewed method plus its declared runtime modules. Those modules load before confinement; this is the `94d2295` CI fix.
